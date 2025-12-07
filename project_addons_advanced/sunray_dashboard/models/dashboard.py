import ast
import json
import logging
import traceback
import pprint

from dateutil.relativedelta import relativedelta

from odoo.exceptions import UserError
from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval
from functools import lru_cache
import hashlib
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


DASHBOARD_TYPE_LIST = [
    ('bar', 'Bar'),
    ('line', 'Line'),
    ('pie', 'Pie'),
    ('mix', 'Mix'),
    ('number', 'Number'),
    ('list', 'List')
]

DEFAULT_BAR_INLINE_CODE = """# Enter python code below.
# Available vars:
#   - self: The dashboard object.
#   - dash_cr: database cursor.
#   - relativedelta: method from relativedelta.
#   - current_date<Datime>: The current datetime.
#   - result_dict: A dict which contains data to append.
#
# Result:
#   let result_dict with the result. Eg.
#   result_dict = {
#       'result_list': [
#           {
#               'label': '01-21',
#               'value': 5,
#               'type': 'past'
#           }
#       ],
#       'model_name': 'model.x', # Name of the model of the dashboard
#       'action_domain: [('state', '=', 'wip')], # A domain that will be passed to the action
#       'action_context': {'group_by': 'start_date:month'},
#       'configuration_dict': # Optional var. Used to indicate to the user that configuration is required and redirects the user to a new model form view.
#       { 
#           'display': True if len(model_objs) == 0 else False, # A condition for displaying the configuration. Default is False.
#           'message': "A display message", # A message that will be displayed if configuration is needed. Default is "".
#           'action_context': {}, # optionnal key
#           'action_domain': [], # optionnal key
#           'action_name': 'module.action_id', #optionnal key. If specify, it will open this action instead of the default one,
#           'model_name': 'model.name' # optionnal key. Allow to specify an other model for the configuration. If not the model_name of the configuration will be the global 'model_name'
#       }
#   }
#"""
DEFAULT_LINE_INLINE_CODE = """# Enter python code below.
# Available vars:
#   - self: The dashboard object.
#   - dash_cr: database cursor.
#   - relativedelta: method from relativedelta.
#   - current_date<Datime>: The current datetime.
#   - result_dict: A dict which contains data to append.
#
# Result:
#   let result_dict with the result. Eg.
#   result_dict = {
#       'result_list': [
#           {
#               'x': '01-21',
#               'y': 5,
#               'name': '01-21'
#           },
#       ],
#       'model_name': 'model.x', # Name of the model of the dashboard
#       'action_domain: [('state', '=', 'wip')], # A domain that will be passed to the action
#       'action_context': {'group_by': 'start_date:month'},
#       'configuration_dict': # Optional var. Used to indicate to the user that configuration is required and redirects the user to a new model form view.
#       { 
#           'display': True if len(model_objs) == 0 else False, # A condition for displaying the configuration. Default is False.
#           'message': "A display message", # A message that will be displayed if configuration is needed. Default is "".
#           'action_context': {}, # optionnal key
#           'action_domain': [], # optionnal key
#           'action_name': 'module.action_id', #optionnal key. If specify, it will open this action instead of the default one,
#           'model_name': 'model.name' # optionnal key. Allow to specify an other model for the configuration. If not the model_name of the configuration will be the global 'model_name'
#       }
#   }
#"""
DEFAULT_PIE_INLINE_CODE = """# Enter python code below.
# Available vars:
#   - self: The dashboard object.
#   - dash_cr: database cursor.
#   - relativedelta: method from relativedelta.
#   - current_date<Datime>: The current datetime.
#   - result_dict: A dict which contains data to append.
#
# Result:
#   let result_dict with the result. Eg.
#   result_dict = {
#       'result_list': [
#           {
#               'label': '01-21',
#               'value': 5
#           },
#       ],
#       'model_name': 'model.x', # Name of the model of the dashboard
#       'action_domain: [('state', '=', 'wip')], # A domain that will be passed to the action
#       'action_context': {'group_by': 'start_date:month'},
#       'configuration_dict': # Optional var. Used to indicate to the user that configuration is required and redirects the user to a new model form view.
#       { 
#           'display': True if len(model_objs) == 0 else False, # A condition for displaying the configuration. Default is False.
#           'message': "A display message", # A message that will be displayed if configuration is needed. Default is "".
#           'action_context': {}, # optionnal key
#           'action_domain': [], # optionnal key
#           'action_name': 'module.action_id', #optionnal key. If specify, it will open this action instead of the default one,
#           'model_name': 'model.name' # optionnal key. Allow to specify an other model for the configuration. If not the model_name of the configuration will be the global 'model_name'
#       }
#   }
#"""
DEFAULT_MIX_INLINE_CODE = """# Enter python code below.
# Available vars:
#   - self: The dashboard object.
#   - dash_cr: database cursor.
#   - relativedelta: method from relativedelta.
#   - current_date<Datime>: The current datetime.
#   - result_dict: A dict which contains data to append.
#
# Result:
#   let result_dict with the result. Eg.
#   result_dict = {
#       'result_list': [
#           {
#               'label': '01-21',
#               'first_chart_value': 5,
#               'second_chart_value': 10,
#           },
#       ],
#       'model_name': 'model.x', # Name of the model of the dashboard
#       'action_domain': [('state', '=', 'wip')], # A domain that will be passed to the action
#       'action_context': {'group_by': 'start_date:month'}
#       'configuration_dict': # Optional var. Used to indicate to the user that configuration is required and redirects the user to a new model form view.
#       { 
#           'display': True if len(model_objs) == 0 else False, # A condition for displaying the configuration. Default is False.
#           'message': "A display message", # A message that will be displayed if configuration is needed. Default is "".
#           'action_context': {}, # optionnal key
#           'action_domain': [], # optionnal key
#           'action_name': 'module.action_id', #optionnal key. If specify, it will open this action instead of the default one,
#           'model_name': 'model.name' # optionnal key. Allow to specify an other model for the configuration. If not the model_name of the configuration will be the global 'model_name'
#       }
#   }
#"""
DEFAULT_NUMBER_INLINE_CODE = """# Enter python code below.
# Available vars:
#   - self: The dashboard object.
#   - dash_cr: database cursor.
#   - relativedelta: method from relativedelta.
#   - current_date<Datime>: The current datetime.
#   - result_dict: A dict which contains data to append.
#
# Result:
#   let result_dict with the result. Eg.
#   result_dict = {
#       'result_list': [
#           {
#               'number': 5, # Number displayed
#               'text': 'Title' # Name of the text that is displayed
#           },
#       ],
#       'model_name': 'model.x', # Name of the model of the dashboard
#       'action_domain: [('state', '=', 'wip')], # A domain that will be passed to the action
#       'action_context': {'group_by': 'start_date:month'}
#       'configuration_dict': # Optional var. Used to indicate to the user that configuration is required and redirects the user to a new model form view.
#       { 
#           'display': True if len(model_objs) == 0 else False, # A condition for displaying the configuration. Default is False.
#           'message': "A display message", # A message that will be displayed if configuration is needed. Default is "".
#           'action_context': {}, # optionnal key
#           'action_domain': [], # optionnal key
#           'action_name': 'module.action_id', #optionnal key. If specify, it will open this action instead of the default one,
#           'model_name': 'model.name' # optionnal key. Allow to specify an other model for the configuration. If not the model_name of the configuration will be the global 'model_name'
#       }
#   }
#"""
DEFAULT_LIST_INLINE_CODE = """# Enter python code below.
# Available vars:
#   - self: The dashboard object.
#   - dash_cr: database cursor.
#   - relativedelta: method from relativedelta.
#   - current_date<Datime>: The current datetime.
#   - result_dict: A dict which contains data to append.
#
# Result:
#   let result_dict with the result. Eg.
#   result_dict = {
#       'result_list': [
#           {
#               'headers': ['Header1', 'Header2'], # Headers in list
#               'rows': [(1, '2022'), (2, '2023'), (1, '2022'), (1, '2022'),] # Tuple data in a list
#           },
#       ],
#       'model_name': 'model.x', # Name of the model of the dashboard
#       'action_domain: [('state', '=', 'wip')], # A domain that will be passed to the action
#       'action_context': {'group_by': 'start_date:month'}
#       'configuration_dict': # Optional var. Used to indicate to the user that configuration is required and redirects the user to a new model form view.
#       { 
#           'display': True if len(model_objs) == 0 else False, # A condition for displaying the configuration. Default is False.
#           'message': "A display message", # A message that will be displayed if configuration is needed. Default is "".
#           'action_context': {}, # optionnal key
#           'action_domain': [], # optionnal key
#           'action_name': 'module.action_id', #optionnal key. If specify, it will open this action instead of the default one,
#           'model_name': 'model.name' # optionnal key. Allow to specify an other model for the configuration. If not the model_name of the configuration will be the global 'model_name'
#       }
#   }
#"""

class SunrayDashboard(models.Model):
    _name = 'sunray.dashboard'
    _description = 'Dashboard - Sunray'
    _order = "sequence"

    # def _get_kanban_datas(self):
    #     return json.dumps({
    #         'x_field': 'x'
    #     })


    name = fields.Char()
    sequence = fields.Integer(default=1)
    description = fields.Char()
    active = fields.Boolean(default=True)
    # kanban_dashboard = fields.Text(compute='_get_kanban_datas')
    kanban_dashboard_graph = fields.Text(compute='_get_graph')
    kanban_dashboard_type = fields.Selection(
        DASHBOARD_TYPE_LIST, 
        string="Type", 
        help="Type of the dashboard.",
        default='bar',
        required=True
    )
    inline_code = fields.Text(string="Inline Code", default=DEFAULT_BAR_INLINE_CODE)
    background_color = fields.Char(string="Background Color", help="Background Color in hex. Eg: '#875A7B'")
    border_color = fields.Char(string="Border Color", help="Border Color in hex. Eg: '#875A7B'")
    bar_color = fields.Char(string="Color", help="Border Color in hex. Eg: '#875A7B'")
    
    # Params for Mix Chart
    mix_first_label = fields.Char(string="First Chart Label", help="Label for the first chart.")
    mix_second_label = fields.Char(string="Second Chart Label", help="Label for the second chart.")
    mix_first_type = fields.Selection(
        [('bar', 'Bar'), ('line', 'Line')], 
        string="First Type",
        default='bar',
        help="Type of the first chart."
    )
    mix_second_type = fields.Selection(
        [('bar', 'Bar'), ('line', 'Line')],
        string="Second Type",
        default='bar',
        help="Type of the second chart."
    )
    mix_first_color = fields.Char(string="First Chart Color", help="Color for the first chart in hex. Eg: '#875A7B'")
    mix_second_color = fields.Char(string="Second Chart Color", help="Color of the second chart in hex. Eg: '#875A7B'")
    model_name = fields.Char(string="Model Name", help="Name of the model of datas. ")
    action_domain = fields.Char(string="Action Domain", help="A domain for the action that will display datas.")
    action_context = fields.Char(string="Action Context", help="A context for the action that will display datas.")
    display_label_x = fields.Boolean(
        string="Display Label Axis X",
        help="When checked, display label for axis X on graph",
        default=True
    )
    display_label_y = fields.Boolean(
        string="Display Label Axis Y",
        help="When checked, display label for axis Y on graph",
        default=False
    )
    configuration_data = fields.Text(compute='_get_graph')


    @api.onchange('kanban_dashboard_type')
    def _onchange_kanban_dashboard_type(self):
        if self.kanban_dashboard_type and not self._origin.kanban_dashboard_type:
            if self.kanban_dashboard_type == 'line':
                self.inline_code = DEFAULT_LINE_INLINE_CODE
            elif self.kanban_dashboard_type == 'bar':
                self.inline_code = DEFAULT_BAR_INLINE_CODE
            elif self.kanban_dashboard_type == 'pie':
                self.inline_code = DEFAULT_PIE_INLINE_CODE
        elif self.kanban_dashboard_type and self._origin.kanban_dashboard_type:
            old_text = 'DEFAULT_%s_INLINE_CODE' % self._origin.kanban_dashboard_type.upper()
            new_text = 'DEFAULT_%s_INLINE_CODE' % self.kanban_dashboard_type.upper()
            self.inline_code = self.inline_code.replace(globals()[old_text], globals()[new_text])
    
    @lru_cache(maxsize=128)
    def _get_compiled_code(self, code_hash, inline_code):
        """Cache des scripts compilés pour éviter de recompiler à chaque fois"""
        return compile(inline_code, '<dashboard>', 'exec')
    
    def dashboard_compute__inline(self):
        """ Compute invoiced qty using user defined expression.
        :returns: A list of dict. 
        """
        current_date = fields.Datetime.now()

        # Optimisation : compiler le code une seule fois
        code_hash = hashlib.md5(self.inline_code.encode()).hexdigest()
        compiled_code = self._get_compiled_code(code_hash, self.inline_code)

        db_name = self.env.cr.dbname
        with Registry(db_name).cursor() as new_cr: 
            exec_env = {
                'self': self,
                'relativedelta': relativedelta,
                'current_date': current_date,
                "dash_cr": new_cr,  # Dashboard must use this cr for queries
                'print': print,
                'result_dict': {}
            }
            # Utiliser le code compilé au lieu de safe_eval
            exec(compiled_code, exec_env)
            _result = exec_env.get('result_dict')
            return _result
    
        #db_name = self.env.cr.dbname
        #db = db_connect(db_name)  # Open indépdante db cnx
        #with db.cursor() as new_cr: 
        #    exec_env = {
        #        'self': self,
        #        'cr': new_cr,
        #        'relativedelta': relativedelta,
        #        'current_date': current_date,
        #        # 'result_list': [],
        #        'print': print,
        #        'result_dict': {}
        #    }
        #    try:
        #        safe_eval(
        #            self.inline_code, 
        #            locals_dict=exec_env, 
        #            mode='exec',
        #            nocopy=True
        #        )
        #        new_cr.commit()
        #        _result = exec_env.get('result_dict')
        #        return _result
        #    except:
        #        new_cr.rollback()
        #        raise



    def _get_graph_datas(self, data):
        """Computes the data used to display the graph in the dashboard"""
        graph_params = [{
            'values': data, 
            'title': '', 
            'key': self.name, 
            'is_sample_data': False,
        }]
        if self.kanban_dashboard_type == 'line':
            graph_params[0]['area'] = True
            graph_params[0]['backgroundColor'] = self.background_color
            graph_params[0]['borderColor'] = self.border_color
        elif self.kanban_dashboard_type == 'bar':
            graph_params[0]['barColor'] = self.bar_color
        elif self.kanban_dashboard_type == 'mix':
            graph_params[0]['firstChartLabel'] = self.mix_first_label
            graph_params[0]['secondChartLabel'] = self.mix_second_label
            graph_params[0]['firstChartType'] = self.mix_first_type
            graph_params[0]['secondChartType'] = self.mix_second_type
            graph_params[0]['firstChartColor'] = self.mix_first_color
            graph_params[0]['secondChartColor'] = self.mix_second_color
        graph_params[0]['displayLabelX'] = self.display_label_x
        graph_params[0]['displayLabelY'] = self.display_label_y
        return graph_params

    def _get_graph(self):
        for record in self:
            try:
                result_dict = record.dashboard_compute__inline()
                record.model_name = result_dict.get('model_name', None)
                record.action_domain = result_dict.get('action_domain', [])
                record.action_context = result_dict.get('action_context', {})
                record.kanban_dashboard_graph = json.dumps(record._get_graph_datas(result_dict.get('result_list',[])))
                config_dict = result_dict.get('configuration_dict', {})
                config_dict['res_model'] = config_dict.get('model_name', result_dict.get('model_name', None))

            except:
                result_dict = {}
                record.kanban_dashboard_type = 'list'
                record.kanban_dashboard_graph =  json.dumps([{
                    'values': [], 
                    'title': '', 
                    'key': record.name, 
                    'is_sample_data': False,
                }])

                #record.model_name = result_dict.get('model_name', None)
                #record.action_domain = result_dict.get('action_domain', [])
                #record.action_context = result_dict.get('action_context', {})
                config_dict = {
                    'display': True,
                    'message': "An issue has occurred with this dashboard. Please review the errors in the 'Configuration Data' tab.",
                    'error': traceback.format_exc().split('\n')
                }
            record.configuration_data = json.dumps(config_dict, indent=4)

    def _select_action_to_open(self):
        """Return act_window from the model_name"""
        self.ensure_one()
        action = False
        return action

    def open_action(self):
        """returns action based on model"""
        self.ensure_one()
        action_name = self._select_action_to_open()
        if action_name:
            action = self.env["ir.actions.act_window"]._for_xml_id(action_name)
            if action:
                action['domain'] = ast.literal_eval(self.action_domain)
                action['context'] = self.action_context
                action['name'] = self.name
                action['display_name'] = self.name
                return action
            else:
                raise UserError("No action found for model %s" % self.model_name)

    def open_configuration_action_name(self, action_name):
        action = self.env["ir.actions.act_window"]._for_xml_id(action_name)