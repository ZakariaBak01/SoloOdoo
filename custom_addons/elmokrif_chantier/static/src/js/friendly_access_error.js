/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { WarningDialog } from "@web/core/errors/error_dialogs";
import { registry } from "@web/core/registry";

class FriendlyAccessErrorDialog extends WarningDialog {
    setup() {
        super.setup();
        this.title = _t("Access denied");
        this.message = _t(
            "You do not have permission to access this page or record. Please contact your administrator if you need access."
        );
    }
}

registry
    .category("error_dialogs")
    .add("odoo.exceptions.AccessError", FriendlyAccessErrorDialog, { force: true });
