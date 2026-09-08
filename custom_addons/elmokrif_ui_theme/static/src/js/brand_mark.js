/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class ElMokriefBrandMark extends Component {
    static template = "elmokrif_ui_theme.ElMokriefBrandMark";
}

registry.category("systray").add(
    "elmokrif_ui_theme.brand_mark",
    { Component: ElMokriefBrandMark },
    { sequence: 5 }
);
