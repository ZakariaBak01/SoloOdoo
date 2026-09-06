FROM odoo:17.0

COPY custom_addons /opt/elmokrif-addons
USER root
RUN sed -i 's#addons_path = /mnt/extra-addons#addons_path = /mnt/extra-addons,/opt/elmokrif-addons#' /etc/odoo/odoo.conf
USER odoo
