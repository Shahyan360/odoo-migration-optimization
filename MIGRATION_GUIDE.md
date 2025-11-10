# Custom addon migration: 17 to 18

The primary addons/ directory targets Odoo 18. versions/17.0/addons/ contains the
independently authored Odoo 17 variant. Use separate databases and versions;
never point Odoo 18 directly at an unupgraded Odoo 17 database.

1. Install the 17 variant in an isolated 17 environment and configure fictional
   locations, products and data. Back up only that personal demo if desired.
2. Choose an authorized official database-upgrade path or a separately researched
   OpenUpgrade path for the native Odoo database. This repository does not provide
   a core database migration engine or original client migration scripts.
3. Replace the custom addons mount with the Odoo 18 variant, update the manifest
   version, and upgrade this addon after the native database has been upgraded.
4. Review tree-to-list view changes, stock product type (17: type=product;
   18: is_storable=True), Query/SQL APIs, ACL external IDs and company rules.
5. The pre-migration hook illustrates a safe conditional custom-column rename.
   Both released variants already use lab_material_class; the hook is only
   applicable to an explicitly created legacy-column example.
6. Compare product classification, location boundaries, quantities and baseline/
   optimized results. Record any actual regressions and measurements later.

Both source variants and the migration hook are implemented; execution validation was deferred by request.
There is no claimed historical migration, preserved production database, or
guarantee that a source-code change alone upgrades Odoo's native schema.
