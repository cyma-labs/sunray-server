/** @odoo-module **/

import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";

const userMenuRegistry = registry.category("user_menuitems");

function sunrayAccessControlItem() {
    return {
        type: "item",
        id: "sunray_access_control",
        description: _t("Sunray Access Control"),
        callback: () => {
            browser.location = "/sunray/help";
        },
        sequence: 65,
    };
}

userMenuRegistry.add("sunray_access_control", sunrayAccessControlItem);
