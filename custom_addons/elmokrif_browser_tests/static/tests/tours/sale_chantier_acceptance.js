/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("elmokrif_sale_chantier_send", {
    test: true,
    steps: () => [
        {
            content: "The salesperson can see the quotation's header chantier",
            trigger: '.o_form_view:contains("Browser Site A")',
        },
        {
            content: "The first quotation line is allocated to Site A",
            trigger: '.o_field_one2many[name="order_line"] .o_data_row td[name="chantier_id"]:contains("Browser Site A")',
        },
        {
            content: "The second quotation line is allocated to Site B",
            trigger: '.o_field_one2many[name="order_line"] .o_data_row td[name="chantier_id"]:contains("Browser Site B")',
        },
        {
            content: "Open the quotation email composer",
            trigger: '.o_statusbar_buttons button[name="action_quotation_send"]',
            run: "click",
        },
        {
            content: "Send the quotation from the composer",
            trigger: '.modal-footer button[name="action_send_mail"]',
            run: "click",
        },
        {
            content: "The quotation is now sent",
            trigger: '.o_statusbar_buttons > button[name="action_confirm"]:first-child',
        },
    ],
});

registry.category("web_tour.tours").add("elmokrif_sale_chantier_confirm", {
    test: true,
    steps: () => [
        {
            content: "The sent quotation still exposes line allocation",
            trigger: '.o_field_one2many[name="order_line"] td[name="chantier_id"]:contains("Browser Site B")',
        },
        {
            content: "Confirm the quotation",
            trigger: '.o_statusbar_buttons button[name="action_confirm"]',
            run: "click",
        },
    ],
});

registry.category("web_tour.tours").add("elmokrif_sale_chantier_invoice", {
    test: true,
    steps: () => [
        {
            content: "The accountant sees Site A on its invoice line",
            trigger: '.o_field_one2many[name="invoice_line_ids"] .o_data_row td[name="chantier_id"]:contains("Browser Site A")',
        },
        {
            content: "The accountant sees Site B on its invoice line",
            trigger: '.o_field_one2many[name="invoice_line_ids"] .o_data_row td[name="chantier_id"]:contains("Browser Site B")',
        },
        {
            content: "Post the invoice as the accountant",
            trigger: '.o_statusbar_buttons button[name="action_post"]',
            run: "click",
        },
    ],
});
