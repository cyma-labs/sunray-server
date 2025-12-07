/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const COLORS = ["#1f77b4","#ff7f0e","#aec7e8","#7f7f7f","#c7c7c7","#17becf","#9edae5",
    "#ffbb78","#2ca02c","#98df8a","#d62728","#ff9896","#9467bd","#c5b0d5",
    "#8c564b","#c49c94","#e377c2","#f7b6d2","#bcbd22","#dbdb8d"];

export class SunrayDashboardGraph extends Component {
    static template = "sunray_dashboard.SunrayDashboardGraph";
    static props = {
        ...standardFieldProps,
        graph_type: { type: String, optional: true },
        configuration_data: { type: String, optional: true },
    };

    setup() {
        this.canvasRef = useRef("canvas");
        this.actionService = useService("action");
        this.chart = null;

        // In Odoo 18, retrieve graph_type from XML attributes
        this.graph_type = this.props.graph_type || this.props.attrs?.graph_type;

        // Correct access to field data in Odoo 18
        const fieldValue = this.props.record.data[this.props.name];
        const configurationDataField = this.props.record.data['configuration_data'];
        this.data = fieldValue ? JSON.parse(fieldValue) : [];
        this.configurationData = configurationDataField ? JSON.parse(configurationDataField) : {};

        // Extract configuration display settings for template
        this.configurationDisplay = this.configurationData?.display || false;
        this.configurationMessage = this.configurationData?.message || 'Configuration required';
        this.displayConfigurationButton = this.configurationData?.display_configuration_button || false;

        onMounted(() => {
            this._renderChart();
        });

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
            }
        });
    }

    _renderChart() {
        if (!this.canvasRef.el) return;

        // Handle different dashboard types
        if (this.graph_type === 'list') {
            this._renderTable();
        } else if (this.graph_type === 'number') {
            this._renderNumber();
        } else {
            // Chart types (line, bar, pie, mix)
            const config = this._getChartConfig();
            if (!config) return;

            // Performance optimization: Update data instead of recreating chart if possible
            if (this.chart && this.chart.config.type === config.type) {
                this.chart.data = config.data;
                this.chart.options = config.options;
                this.chart.update('none'); // No animation for better performance
            } else {
                // Destroy existing chart if any
                if (this.chart) {
                    this.chart.destroy();
                }

                const ctx = this.canvasRef.el.getContext('2d');
                this.chart = new Chart(ctx, config);
            }
        }
    }

    _getChartConfig() {
        if (!this.data || !this.data[0]) return null;

        switch (this.graph_type) {
            case 'line':
                return this._getLineChartConfig();
            case 'bar':
                return this._getBarChartConfig();
            case 'pie':
                return this._getPieChartConfig();
            case 'mix':
                return this._getMixChartConfig();
            default:
                return null;
        }
    }

    _getLineChartConfig() {
        const labels = this.data[0].values.map(pt => pt.x);
        const borderColor = this.data[0].borderColor;
        const backgroundColor = this.data[0].backgroundColor;
        
        return {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    data: this.data[0].values,
                    fill: 'start',
                    label: this.data[0].key,
                    backgroundColor: backgroundColor,
                    borderColor: borderColor,
                    borderWidth: 2,
                }]
            },
            options: {
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { display: this.data[0].displayLabelY },
                    x: { display: this.data[0].displayLabelX }
                },
                maintainAspectRatio: false,
                elements: {
                    line: {
                        tension: 0.000001
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                },
            },
        };
    }

    _getBarChartConfig() {
        const data = [];
        const labels = [];
        const backgroundColor = [];
        const color = this.data[0].barColor;
        
        this.data[0].values.forEach(pt => {
            data.push(pt.value);
            labels.push(pt.label);
            backgroundColor.push(color);
        });
        
        return {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    fill: 'start',
                    label: this.data[0].key,
                    backgroundColor: backgroundColor,
                }]
            },
            options: {
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: { display: this.data[0].displayLabelY },
                    x: { display: this.data[0].displayLabelX }
                },
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                },
                elements: {
                    line: {
                        tension: 0.000001
                    }
                },
            },
        };
    }

    _getPieChartConfig() {
        const counts = this.data[0].values.map(point => point.value);
        
        return {
            type: 'pie',
            data: {
                labels: this.data[0].values.map(point => point.label),
                datasets: [{
                    label: '',
                    data: counts,
                    backgroundColor: counts.map((val, index) => COLORS[index % 20]),
                }]
            },
            options: {
                maintainAspectRatio: false,
            }
        };
    }

    _getMixChartConfig() {
        const firstChartData = [];
        const secondChartData = [];
        const labels = [];

        this.data[0].values.forEach(pt => {
            firstChartData.push(pt.first_chart_value);
            secondChartData.push(pt.second_chart_value);
            labels.push(pt.label);
        });

        return {
            type: this.data[0].firstChartType,
            data: {
                datasets: [{
                    label: this.data[0].firstChartLabel,
                    data: firstChartData,
                    order: 1,
                    backgroundColor: this.data[0].firstChartColor
                }, {
                    label: this.data[0].secondChartLabel,
                    data: secondChartData,
                    type: this.data[0].secondChartType,
                    order: 2,
                    backgroundColor: this.data[0].secondChartColor
                }],
                labels: labels
            },
            options: {
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    y: {
                        display: false,
                        beginAtZero: true
                    }
                },
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'nearest'
                },
                elements: {
                    line: {
                        tension: 0.000001
                    }
                },
            },
        };
    }

    _renderTable() {
        if (!this.data || !this.data[0]) return;
        
        if (this.data[0].values && this.data[0].values.length > 0) {
            const tableData = this.data[0].values[0];
            if (!tableData || !tableData.headers || !tableData.rows) return;
            
            let html = '<div class="o_sunray_dashboard_content_list">';
            html += '<table class="table table-sm o_main_table">';
            
            // Headers
            html += '<thead><tr>';
            tableData.headers.forEach(header => {
                html += `<th>${header}</th>`;
            });
            html += '</tr></thead>';
            
            // Rows
            html += '<tbody>';
            tableData.rows.forEach(row => {
                html += '<tr>';
                row.forEach(cell => {
                    html += `<td>${cell}</td>`; // HTML not escaped for badges/links
                });
                html += '</tr>';
            });
            html += '</tbody></table></div>';
            
            this.canvasRef.el.innerHTML = html;
        }
        else if (this.configurationData && this.configurationData.display) {
            this._renderConfiguration();
        }
        else {
            this.canvasRef.el.innerHTML = '<div class="text-center p-3"></div>';
        }
    }
    
    _renderConfiguration() {
        if (!this.configurationData || !this.configurationData.display) return;

        let html = '<div class="o_sunray_dashboard_content">';
        html += '<div class="o_sunray_dashboard_configuration">';
        html += `<p class="o_sunray_dashboard_configuration_message">${this.configurationData.message || 'Configuration required'}</p>`;

        // Button to open configuration action if display_configuration_button is true
        if (this.displayConfigurationButton && this.configurationData.res_model) {
            html += '<div class="o_sunray_dashboard_configuration_link">';
            html += '<button class="btn btn-warning" id="config_button_' + this.props.record.resId + '">Configurer</button>';
            html += '</div>';
        }

        html += '</div></div>';

        this.canvasRef.el.innerHTML = html;

        // Attach event listener to button if it exists
        if (this.displayConfigurationButton && this.configurationData.res_model) {
            const button = this.canvasRef.el.querySelector('#config_button_' + this.props.record.resId);
            if (button) {
                button.addEventListener('click', (e) => {
                    e.stopPropagation(); // Prevent triggering openConfigurationAction
                    this.openButtonConfigurationFormView();
                });
            }
        }
    }

    _renderNumber() {
        if (!this.data || !this.data[0] || !this.data[0].values) return;
        
        const numberData = this.data[0].values[0];
        if (!numberData) return;
        
        let html = '<div style="height: 100%; width: 100%;">';
        html += '<div style="height: 70%;">';
        html += `<p class="text-center" style="height: 100%;font-size: 55px;padding-top: 34px;">${numberData.number}</p>`;
        html += '</div>';
        html += '<div>';
        html += `<p class="text-center" style="height: 100%;font-size: 22px;">${numberData.text}</p>`;
        html += '</div></div>';
        
        this.canvasRef.el.innerHTML = html;
    }

    openConfigurationAction() {
        // Priorité 1: Action de configuration depuis configurationData
        if (this.configurationData && this.configurationData.res_model) {
            const actionName = this.configurationData.action_name || false;

            if (actionName) {
                this.actionService.doAction(actionName);
            } else {
                this.actionService.doAction({
                    type: 'ir.actions.act_window',
                    res_model: this.configurationData.res_model,
                    views: [[false, 'list'], [false, 'form']],
                    context: this.configurationData.action_context || {},
                    domain: this.configurationData.action_domain || []
                });
            }
            return;
        }

        // Priorité 2: Action depuis les données du dashboard (legacy)
        if (this.data && this.data[0] && this.data[0].configurationData) {
            try {
                const configurationData = JSON.parse(this.data[0].configurationData);
                const actionName = configurationData.action_name || false;

                if (actionName) {
                    this.actionService.doAction(actionName);
                } else {
                    this.actionService.doAction({
                        type: 'ir.actions.act_window',
                        res_model: configurationData['res_model'],
                        views: [[false, 'list'], [false, 'form']],
                        context: configurationData.action_context || {},
                        domain: configurationData.action_domain || []
                    });
                }
            } catch (error) {
                console.error('Erreur lors de l\'ouverture de l\'action de configuration:', error);
            }
        }
    }

    openButtonConfigurationFormView() {
        // Ouvre directement la vue formulaire du modèle spécifié dans configurationData
        if (!this.configurationData || !this.configurationData.res_model) {
            console.error('No res_model defined in configurationData');
            return;
        }

        const actionName = this.configurationData.action_name || false;

        if (actionName) {
            // Si une action nommée est spécifiée, l'utiliser
            this.actionService.doAction(actionName);
        } else {
            // Sinon, ouvrir directement en vue formulaire
            this.actionService.doAction({
                type: 'ir.actions.act_window',
                res_model: this.configurationData.res_model,
                views: [[false, 'form']],
                target: 'current',
                context: this.configurationData.action_context || {},
            });
        }
    }
}

export const sunrayDashboardGraphField = {
    component: SunrayDashboardGraph,
    supportedTypes: ["text"],
    extractProps: ({ attrs, record }) => ({
        graph_type: attrs.graph_type,
        configuration_data: attrs.configuration_data,
        record: record,
    }),
};


registry.category("fields").add("SunrayDashboardGraph", sunrayDashboardGraphField);