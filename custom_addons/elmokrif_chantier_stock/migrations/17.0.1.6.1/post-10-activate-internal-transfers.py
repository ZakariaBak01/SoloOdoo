def migrate(cr, version):
    cr.execute(
        """
        UPDATE stock_picking_type
           SET active = TRUE
         WHERE active = FALSE
           AND id IN (
               SELECT int_type_id
                 FROM stock_warehouse
                WHERE int_type_id IS NOT NULL
           )
        """
    )
