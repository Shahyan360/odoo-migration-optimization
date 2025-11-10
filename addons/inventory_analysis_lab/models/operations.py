import statistics
import time
from datetime import datetime,timedelta
from odoo import api,fields,models
from odoo.exceptions import UserError,ValidationError
from odoo.tools import SQL
from ..common import guard

class Product(models.Model):
    _inherit='product.template'
    lab_material_class=fields.Selection([('raw','Raw Material'),('finished','Finished Product')],string='Analysis Material Class')

class Analysis(models.Model):
    _name='inventory.analysis.run'
    _description='Measured Inventory Movement Analysis'
    name=fields.Char(required=True,default='Synthetic inventory analysis')
    company_id=fields.Many2one('res.company',required=True,default=lambda s:s.env.company)
    location_ids=fields.Many2many('stock.location',string='Internal Location Roots',required=True)
    date_from=fields.Date(required=True,default=lambda s:fields.Date.context_today(s)-timedelta(days=30))
    date_to=fields.Date(required=True,default=fields.Date.context_today)
    repetitions=fields.Integer(default=3,required=True)
    slow_seconds=fields.Float(readonly=True)
    optimized_seconds=fields.Float(readonly=True)
    measurements=fields.Json(readonly=True)
    rows=fields.Json(readonly=True)
    state=fields.Selection([('draft','Not Measured'),('measured','Measured')],default='draft',readonly=True)
    synthetic_products=fields.Integer(default=20)
    synthetic_movements=fields.Integer(default=500)

    @api.constrains('date_from','date_to','repetitions','synthetic_movements','synthetic_products','location_ids')
    def _check(self):
        for run in self:
            if run.date_to<run.date_from or not 1<=run.repetitions<=10 or not 1<=run.synthetic_products<=200 or not 1<=run.synthetic_movements<=20000:
                raise ValidationError('Use a valid date range and bounded repetition/data sizes.')
            if any(l.usage!='internal' or (l.company_id and l.company_id!=run.company_id) for l in run.location_ids):
                raise ValidationError('Only internal locations in the report company are supported.')

    def _locations(self):
        self.ensure_one()
        return self.env['stock.location'].search([('id','child_of',self.location_ids.ids),('usage','=','internal'),
                                                  '|',('company_id','=',False),('company_id','=',self.company_id.id)])
    def _domain(self):
        self.ensure_one()
        end=datetime.combine(self.date_to,datetime.max.time())
        return [('state','=','done'),('company_id','=',self.company_id.id),('date','<=',end),
                '|',('location_id','in',self._locations().ids),('location_dest_id','in',self._locations().ids)]

    def _slow(self):
        # Deliberately realistic N+1 baseline, not an artificial sleep.
        domain=self._domain()
        products=self.env['stock.move'].search(domain).product_id
        rows=[]
        start=datetime.combine(self.date_from,datetime.min.time())
        for location in self._locations():
            for product in products:
                opening=period=0.0
                moves=self.env['stock.move'].search(domain+[('product_id','=',product.id),
                    '|',('location_id','=',location.id),('location_dest_id','=',location.id)])
                for move in moves:
                    delta=move.product_qty*((1 if move.location_dest_id==location else 0)-(1 if move.location_id==location else 0))
                    if move.date<start: opening+=delta
                    else: period+=delta
                if opening or period:
                    rows.append({'product':product.id,'location':location.id,'opening':opening,'movement':period,'closing':opening+period})
        return sorted(rows,key=lambda r:(r['product'],r['location']))

    def _optimized(self):
        self.env['stock.move'].flush_model(['product_qty','state','date','company_id','location_id','location_dest_id'])
        # _search returns an ORM Query with access rights and ir.rule filters.
        # SQL aggregates ONLY those visible rows, rather than bypassing record rules.
        query=self.env['stock.move']._search(self._domain())
        visible=query.select(SQL('stock_move.product_id, stock_move.location_id, stock_move.location_dest_id, stock_move.product_qty, stock_move.date'))
        start=datetime.combine(self.date_from,datetime.min.time())
        ids=tuple(self._locations().ids)
        if not ids: return []
        statement=SQL("""WITH visible AS (%s), delta AS (
             SELECT product_id,location_id AS location,-product_qty AS qty,date FROM visible
             UNION ALL SELECT product_id,location_dest_id AS location,product_qty AS qty,date FROM visible)
          SELECT product_id,location,COALESCE(SUM(qty) FILTER (WHERE date < %s),0),
                 COALESCE(SUM(qty) FILTER (WHERE date >= %s),0)
          FROM delta WHERE location IN %s GROUP BY product_id,location
          HAVING ABS(SUM(qty)) > 0.0000001 OR ABS(COALESCE(SUM(qty) FILTER (WHERE date >= %s),0)) > 0.0000001
          ORDER BY product_id,location""",visible,start,start,ids,start)
        self.env.cr.execute(statement)
        return [{'product':p,'location':l,'opening':float(o),'movement':float(m),'closing':float(o+m)} for p,l,o,m in self.env.cr.fetchall()]

    def action_measure(self):
        guard(self,'inventory_analysis_lab.group_manager')
        for run in self:
            slow,fast=[],[]
            for repetition in range(run.repetitions):
                started=time.perf_counter(); baseline=run._slow(); slow.append(time.perf_counter()-started)
                started=time.perf_counter(); result=run._optimized(); fast.append(time.perf_counter()-started)
                left={(r['product'],r['location']):r for r in baseline}
                right={(r['product'],r['location']):r for r in result}
                if left.keys()!=right.keys() or any(abs(left[key][field]-right[key][field])>0.00001 for key in left for field in ('opening','movement','closing')):
                    raise UserError('Baseline and optimized results differ; no benchmark success is recorded.')
            run.write({'slow_seconds':statistics.median(slow),'optimized_seconds':statistics.median(fast),
                       'measurements':{'slow':slow,'optimized':fast,'cache':'warm ORM/database caches; fixed baseline-then-optimized order'},
                       'rows':result,'state':'measured'})
        return True

    def action_generate_synthetic(self):
        guard(self,'inventory_analysis_lab.group_manager')
        for run in self:
            if self.env['product.product'].search_count([('default_code','=like','LAB-ANALYSIS-%')]):
                raise UserError('Synthetic analysis products already exist; reuse them instead of duplicating data.')
            products=self.env['product.product'].create([{'name':'Synthetic Stock Item '+str(i),
                'default_code':'LAB-ANALYSIS-'+str(i),'is_storable':True} for i in range(run.synthetic_products)])
            locations=run._locations()
            if not locations: raise UserError('Select a stock location.')
            supplier=self.env.ref('stock.stock_location_suppliers')
            for i in range(run.synthetic_movements):
                product=products[i%len(products)]; destination=locations[i%len(locations)]
                move=self.env['stock.move'].create({'name':'Fictional synthetic receipt','company_id':run.company_id.id,
                    'product_id':product.id,'product_uom':product.uom_id.id,'product_uom_qty':10,
                    'location_id':supplier.id,'location_dest_id':destination.id})
                move._action_confirm(); move.quantity=10; move.picked=True; move._action_done()
                move.date=datetime.combine(run.date_from-timedelta(days=10)+timedelta(days=i%40),datetime.min.time())
        return True

    def action_create_candidate_index(self):
        guard(self,'base.group_system')
        self.env.cr.execute("CREATE INDEX IF NOT EXISTS lab_move_company_state_date ON stock_move (company_id,state,date)")
        return True
