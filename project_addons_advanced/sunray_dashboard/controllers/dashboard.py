from odoo.http import request, route, Controller
from werkzeug.utils import redirect


class DashboardController(Controller):

    @route('/dashboard/open_record', methods=['GET'], type='http', auth='user', csrf=False)
    def open_record(self, record_id, model_name, **kwargs):
        """Open record form view for a given record and model"""
        record_id = int(record_id)
        record = request.env[model_name].browse(record_id)

        if not record.exists():
            return request.not_found()

        action = request.env['ir.actions.act_window'].search([
            ('res_model', '=', model_name),
            ('target', '=', 'current'),
        ], limit=1)
        
        url = f"/web#id={record_id}&action={action.id}&model={model_name}&view_type=form&cids=&menu_id={kwargs.get('menu_id', '')}"

        return redirect(url)