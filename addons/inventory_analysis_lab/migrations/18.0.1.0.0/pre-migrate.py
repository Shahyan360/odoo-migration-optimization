def migrate(cr, version):
    # An illustrative custom-field migration only, not an Odoo core DB upgrade.
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='product_template' AND column_name='lab_legacy_material_class'")
    old=bool(cr.fetchone())
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='product_template' AND column_name='lab_material_class'")
    new=bool(cr.fetchone())
    if old and not new:
        cr.execute('ALTER TABLE product_template RENAME COLUMN lab_legacy_material_class TO lab_material_class')
