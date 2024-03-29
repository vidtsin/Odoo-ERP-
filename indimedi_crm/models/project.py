# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from datetime import datetime
from odoo.exceptions import UserError, ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'
    _order = 'start_time'

    type_of_view  = fields.Many2one('type.view', string="Type of Work")
    start_datetime = fields.Datetime('Start DateTime', store=True )
    end_date = fields.Date('End DateTime', store=True )
    stop_datetime = fields.Datetime('Stop Datetime',store=True)
    start_date = fields.Date('Start Date')
    unit_amount = fields.Float('Duration', store=True)
    start_time = fields.Float('Start Time',required=True, store=True)
    stop_time = fields.Float('Stop Time',required=True, store=True)
    client_name_sheet = fields.Char('Client Name',compute='_get_project_name')
    total_time = fields.Char(string="Total Time")
    start_time_temp = fields.Char(string="Start Time")
    stop_time_temp = fields.Char(string="Stop Time")
    client_reporting_id = fields.Many2one('client.reporting', string="Client Reporting")
    client_client_id = fields.Many2one('client.client', string="Client Name")
    active = fields.Boolean('Active',default=True)
    

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if 'stop_time' in fields:
            fields.remove('stop_time')
        if 'start_time' in fields:
            fields.remove('start_time')
        return super(AccountAnalyticLine, self).read_group(domain, fields, groupby, offset, limit=limit, orderby=orderby, lazy=lazy)

    @api.onchange('start_time','stop_time')
    def _get_total_rate(self):
        for task in self:
            if float(task.stop_time) <= 24 and float(task.start_time) <= 24:
                if float(task.stop_time) == float(0.0):
                    datetime_diff = 24 - task.start_time
                else:
                    datetime_diff = task.stop_time - task.start_time
                task.unit_amount = float(datetime_diff)
            else:
                raise ValidationError(_('Please fill Start Time & Stop Time in 24 hours format and greater than Start Time.'))


    # replace date in timesheet with set date in task form date
    @api.model
    def create(self, vals):
        timesheet = super(AccountAnalyticLine, self).create(vals)
        # timesheet.client_client_id.sudo().write({'task_client_id':timesheet.task_id.id})
        for line in timesheet:
            if line.unit_amount < float(0.0):
                raise ValidationError(_('Please fill Stop Time in 24 hours format and greater than Start Time.'))
        return timesheet


    @api.multi
    def write(self, vals):        
        time = super(AccountAnalyticLine, self).write(vals)
        for line in self:
            if line.unit_amount < float(0.0):
                raise ValidationError(_('Please fill Stop Time in 24 hours format and greater than Start Time.'))
        return time

   


    #for duration calculate automatically in timesheet
    # @api.onchange('start_time','stop_datetime')
    # def _get_total_rate(self):
    #     for task in self:
    #         if task.stop_datetime:
    #             start = datetime.strptime(task.start_datetime, '%Y-%m-%d %H:%M:%S')
    #             task.start_date = start.date()
    #             ends = datetime.strptime(task.stop_datetime, '%Y-%m-%d %H:%M:%S')
    #             datetime_diff = datetime.strptime(task.stop_datetime, '%Y-%m-%d %H:%M:%S') - datetime.strptime(task.start_datetime, '%Y-%m-%d %H:%M:%S')
    #             m, s = divmod(datetime_diff.total_seconds(), 60)
    #             h, m = divmod(m, 60)
    #             dur_h = (_('%0*d')%(2,h))
    #             dur_m = (_('%0*d')%(2,m*1.677966102))
    #             duration = dur_h+'.'+dur_m
    #             task.unit_amount = float(duration) 


    @api.depends('project_id')
    def _get_project_name(self):
        for task in self:
            if task.project_id:
               task.client_name_sheet = str(task.project_id.client_name)


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    @api.multi
    def name_get(self):
        res = []
        for analytic in self:
            name = analytic.name
            if analytic.code:
                name = name
            if analytic.partner_id:
                name = name
            res.append((analytic.id, name))
        return res


class TypeOfView(models.Model):
    _name = 'type.view'

    name = fields.Char(string='Type Of View')
    billable = fields.Boolean(string="Billable")


class ClientClient(models.Model):
    _name = 'client.client'

    name = fields.Char(string="Name")
    task_client_id = fields.Many2one('project.task', string="Client")
