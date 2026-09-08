FROM odoo:17.0

COPY custom_addons /opt/elmokrif-addons
USER root
RUN python3 -m pip install --no-cache-dir websocket-client
RUN sed -i 's#addons_path = /mnt/extra-addons#addons_path = /mnt/extra-addons,/opt/elmokrif-addons#' /etc/odoo/odoo.conf
USER odoo
