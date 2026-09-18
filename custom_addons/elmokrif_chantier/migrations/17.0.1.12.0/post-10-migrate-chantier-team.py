"""Move legacy chantier assignments out of Odoo's personal favorites field."""


def migrate(cr, version):
    cr.execute(
        """
        INSERT INTO project_chantier_user_rel (project_id, user_id)
        SELECT favorite.project_id, favorite.user_id
          FROM project_favorite_user_rel AS favorite
          JOIN project_project AS project
            ON project.id = favorite.project_id
           AND project.is_chantier
          JOIN ir_model_data AS group_data
            ON group_data.module = 'elmokrif_chantier'
           AND group_data.name = 'group_chantier_user'
           AND group_data.model = 'res.groups'
          JOIN res_groups_users_rel AS membership
            ON membership.gid = group_data.res_id
           AND membership.uid = favorite.user_id
          JOIN res_company_users_rel AS company_access
            ON company_access.cid = project.company_id
           AND company_access.user_id = favorite.user_id
          JOIN res_users AS assigned_user
            ON assigned_user.id = favorite.user_id
           AND assigned_user.active
         WHERE favorite.user_id != COALESCE(project.user_id, 0)
        ON CONFLICT DO NOTHING
        """
    )
