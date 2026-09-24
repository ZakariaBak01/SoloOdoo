/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { projectTaskKanbanView } from "@project/views/project_task_kanban/project_task_kanban_view";

class ChantierTaskKanbanController extends KanbanController {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    get projectId() {
        return this.props.context.default_project_id || false;
    }

    get isChantierTaskBoard() {
        return Boolean(this.props.context.is_chantier_task_board);
    }

    async onNewDetailedTask() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "New Detailed Task",
            res_model: "project.task",
            views: [[false, "form"]],
            target: "current",
            context: {
                ...this.props.context,
                default_project_id: this.projectId,
            },
        });
    }

    async onRefreshChantierHealth() {
        await this.orm.call(
            "project.project",
            "action_refresh_chantier_health",
            [[this.projectId]]
        );
        await this.actionService.doAction({ type: "ir.actions.client", tag: "reload" });
    }
}

ChantierTaskKanbanController.template = "elmokrif_chantier.ChantierTaskKanbanView";

registry.category("views").add("chantier_task_kanban", {
    ...projectTaskKanbanView,
    Controller: ChantierTaskKanbanController,
});
