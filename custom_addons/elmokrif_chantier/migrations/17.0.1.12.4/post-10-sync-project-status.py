"""Align existing chantier project-health badges with their lifecycle."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE project_project
           SET last_update_status = CASE chantier_state
               WHEN 'on_hold' THEN 'on_hold'
               WHEN 'completed' THEN 'done'
               WHEN 'closed' THEN 'done'
               ELSE 'on_track'
           END
         WHERE is_chantier = TRUE
        """
    )
