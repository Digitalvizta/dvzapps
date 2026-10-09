import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

export class DvzContractDashboard extends Component {
    static template = "dvz_contract_dashboard.Dashboard";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({ data: null, loading: true });
        onWillStart(() => this.load());
    }

    async load() {
        this.state.loading = true;
        this.state.data = await this.orm.call("dvz.contract", "get_dvz_dashboard_data", []);
        this.state.loading = false;
    }

    openRecord(model, id) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
        });
    }

    openList(model, domain, name) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: model,
            domain: domain,
            views: [[false, "list"], [false, "form"]],
        });
    }

    openAction(xmlId) {
        this.actionService.doAction(xmlId);
    }

    pct(value, max) {
        if (!max) {
            return 0;
        }
        return Math.max(2, Math.min(100, Math.round((value / max) * 100)));
    }

    cap(value) {
        return Math.max(0, Math.min(100, value || 0));
    }

    barClass(percent) {
        if (percent > 100) {
            return "bg-danger";
        }
        if (percent >= 90) {
            return "bg-warning";
        }
        return "bg-success";
    }
}

registry.category("actions").add("dvz_contract_dashboard", DvzContractDashboard);
