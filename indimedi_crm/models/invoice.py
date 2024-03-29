# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
import datetime
import time
import calendar
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT as DF
import dateutil.relativedelta


class TimesheetInvoice(models.Model):
    _name = "timesheet.invoice"
    _inherits = {'account.analytic.account': "analytic_account_id"}
    _order = 'invoice_start_date'

    analytic_account_id = fields.Many2one('account.analytic.account', string='Client Name',
        ondelete="cascade", required=True, auto_join=True)
    invoicing_type_id = fields.Many2one('job.invoicing', string="Invoicing Type")
    invoice_start_date = fields.Date(string="Start Date")
    invoice_end_date = fields.Date(string="End Date")
    hour_selection = fields.Selection([('10','10 Hours'),('20','20 Hours'),('30','30 Hours'),
                                       ('40','40 Hours'),('80','80 Hours'),('90','90 Hours'),
                                       ('100','100 Hours'),('40_20','40-20 Hours'),
                                       ('20_10','20-10 Hours'),('160','160 Hours'),
                                       ('180','180 Hours'),('200','200 Hours')],
                                       string="Working Hours")
    custom_work_hours = fields.Char(string="Working Hours")
    rate_per_hour = fields.Float(string="Rate Per Hour")
    min_bill = fields.Float('Min. Bill')
    worked_hours = fields.Float('Worked Hours')
    ideal_hours = fields.Float('Ideal Hours')
    hours_charged = fields.Float('Hours Charged')
    bill_amount = fields.Float('Bill Amount')
    disc_amount = fields.Float('Disc. Amount')
    final_amount = fields.Float('Final Amount')
    holidays = fields.Float('Holidays', default=0.00)
    billed = fields.Boolean(string="Billed")
    cancelled = fields.Boolean(string="Cancelled")
    sent_mail = fields.Boolean('Sent',default=False)
    invoice_date = fields.Date('Invoice Create Date', default=lambda self: fields.Datetime.now())
    additional_hours = fields.Float(string="Additional Hours")

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, context=None, orderby=False, lazy=True):
        if 'rate_per_hour' in fields:
            fields.remove('rate_per_hour')
        if 'min_bill' in fields:
            fields.remove('min_bill')
        return super(TimesheetInvoice, self).read_group(domain, fields, groupby, offset, limit=limit, orderby=orderby, lazy=lazy)

    @api.onchange('hours_charged')
    def _onchange_bill_amount(self):
        self.bill_amount = self.hours_charged * self.rate_per_hour

    @api.onchange('bill_amount','disc_amount')
    def _onchange_final_amount(self):
        self.final_amount = self.bill_amount - self.disc_amount

    # @api.depends('worked_hours')
    # def _get_ideal_hours(self):
    #     if self.worked_hours < float(self.hour_selection):
    #         self.ideal_hours = float(self.hour_selection) - self.worked_hours

    @api.multi
    def send_timesheet_invoice(self):

        email = str(self.project_ids[0].client_email)
        ctx = dict(email_to=email)
        template = self.env.ref(
            'indimedi_crm.email_template_timesheet_sent')
        self.env['mail.template'].browse(
            template.id).with_context(ctx).send_mail(self.id,force_send=True)
        self.sent_mail = True


    sequence_id = fields.Char('Invoice No.', index=True,readonly=True)

    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('timesheet.invoice') or '/'
        vals['sequence_id'] = seq
        return super(TimesheetInvoice, self).create(vals)



#Schedular for Timesheet Invoice
class Project(models.Model):
    _inherit = 'project.project'

    def _PastweekBoundaries(self, year, week):
        startOfYear = date(year, 1, 1)
        week0 = startOfYear - timedelta(days=startOfYear.isoweekday())
        sun = week0 + timedelta(days = (week-2)*7)
        sat = sun + timedelta(days=6)
        return sun, sat
    # print weekBoundaries(int(dt.year), int(a))

    def _CurrentweekBoundaries(self, year, week):
        startOfYear = date(year, 1, 1)
        week0 = startOfYear - timedelta(days=startOfYear.isoweekday())
        sun = week0 + timedelta(days = (week-1)*7)
        sat = sun + timedelta(days=6)
        return sun, sat
    # print _CurrentweekBoundaries(int(dt.year), int(a))

    def _last_day_of_month(self, any_day):
        next_month = any_day.replace(day=28) + datetime.timedelta(days=4)  # this will never fail
        return next_month - datetime.timedelta(days=next_month.day)


    #This function is called when the weekly scheduler run
    @api.multi
    def weekly_invoice_scheduler_queue(self):

        project_obj = self.search([])
        for project in  project_obj:
            analytic_lines = self.env['account.analytic.account'].search([('project_ids', '=', project.id)])
            if analytic_lines:
                project_rec = analytic_lines.mapped('project_ids')
                if project_rec.invoicing_type_id.name == 'Weekly':
                    for proj in project_rec:

                        dt = datetime.datetime.now()
                        a = datetime.date(int(dt.year), int(dt.month), int(dt.day)).isocalendar()[1]
                        b = int(dt.year)

                        date_in_between = self._PastweekBoundaries(int(b), int(a))
                        week_start = date_in_between[0]
                        week_end = date_in_between[1]

                        #Holiday Count Logic
                        holidays = self.env['public.holiday'].search([
                            ('public_holiday_date', '>=', week_start.strftime(DF)),
                            ('public_holiday_date', '<=', week_end.strftime(DF))])


                        if len(holidays) >= 1.00:
                            daily_hours = float(proj.hour_selection) / 5
                            holidays_hours = daily_hours * len(holidays)
                            custom_work_hours =  round((float(proj.hour_selection) - holidays_hours),2)
                            print "IF>>>>>>custom_work_hours***************",daily_hours, holidays_hours,custom_work_hours
                        else:
                            print "else***************"
                            custom_work_hours = round(float(proj.hour_selection),2)
                            print "ELSE>>>>custom_work_hours***************", custom_work_hours



                        domain = [('project_id', '=', proj.id), ('active', '=', False)]
                        if week_start and week_end:
                            domain.extend([('date', '>=', week_start.strftime(DF)), ('date', '<=', week_end.strftime(DF))])
                        timesheet_lines = self.env['account.analytic.line'].search(domain)

                        sum_hours = sum(timesheet_lines.mapped('unit_amount'))
                        print ">>>", sum_hours
                        if sum_hours < custom_work_hours:
                            ideal_time = custom_work_hours - sum_hours
                        else:
                            ideal_time = 0.00
                        if sum_hours:
                            invoice_lines = self.env['timesheet.invoice'].create({
                                    'analytic_account_id': proj.analytic_account_id.id,
                                    'invoicing_type_id': proj.invoicing_type_id.id,
                                    'invoice_start_date': week_start,
                                    'invoice_end_date': week_end,
                                    'hour_selection': proj.hour_selection,
                                    'custom_work_hours': str(int(custom_work_hours)) + str(' Hours'),
                                    'rate_per_hour': proj.rate_per_hour,
                                    'min_bill': custom_work_hours * proj.rate_per_hour,
                                    'worked_hours': sum_hours,
                                    'ideal_hours': ideal_time,
                                    'hours_charged': sum_hours if sum_hours > custom_work_hours else custom_work_hours,
                                    'bill_amount': (sum_hours if sum_hours > custom_work_hours else custom_work_hours) * proj.rate_per_hour,
                                    'final_amount': (sum_hours if sum_hours > custom_work_hours else custom_work_hours) * proj.rate_per_hour,
                                    'holidays': len(holidays),
                                })

        return True


    #This function is called when the monthly scheduler run
    @api.multi
    def monthly_invoice_scheduler_queue(self):

        project_obj = self.search([])
        for project in  project_obj:
            analytic_lines = self.env['account.analytic.account'].search([('project_ids', '=', project.id)])
            if analytic_lines:
                project_rec = analytic_lines.mapped('project_ids')
                if project_rec.invoicing_type_id.name == 'Monthly':
                    for proj in project_rec:

                        #previous month logic
                        today = date.today()
                        d = today - relativedelta(months=1)
                        month_start = date(d.year, d.month, 1)
                        month_end = date(today.year, today.month, 1) - relativedelta(days=1)

                        #working Days count logic between months
                        start_date = month_start
                        end_date = month_end
                        days = end_date - start_date
                        valid_date_list = {(start_date + datetime.timedelta(days=x)).strftime('%d-%b-%Y')
                                                for x in range(days.days+1)
                                                if (start_date + datetime.timedelta(days=x)).isoweekday() <= 5
                                               }
                        working_days = len(valid_date_list)
                        print "Working Days",working_days
                    
                        #Holiday Count Logic
                        holidays = self.env['public.holiday'].search([
                            ('public_holiday_date', '>=', month_start.strftime(DF)),
                            ('public_holiday_date', '<=', month_end.strftime(DF))])
 
                        if len(holidays) >= 1.00:
                            daily_hours = float(proj.hour_selection) / working_days
                            holidays_hours = daily_hours * len(holidays)
                            custom_work_hours = round((float(proj.hour_selection) - holidays_hours),2)
                            print "IF>>>>>>custom_work_hours***************",daily_hours, holidays_hours
                        else:
                            print "else***************"
                            custom_work_hours = round(float(proj.hour_selection),2)
                            print "ELSE>>>>custom_work_hours***************", custom_work_hours



                        domain = [('project_id', '=', proj.id), ('active', '=', False)]
                        if month_start and month_end:
                            domain.extend([('date', '>=', month_start.strftime(DF)), ('date', '<=', month_end.strftime(DF))])
                        timesheet_lines = self.env['account.analytic.line'].search(domain)
                        
                        sum_hours = sum(timesheet_lines.mapped('unit_amount'))
                        print "sum_hours>>>>>>>>>", sum_hours
                        if sum_hours < float(proj.hour_selection):
                            ideal_time = float(proj.hour_selection) - sum_hours
                        else:
                            ideal_time = 0.00
                        if sum_hours:
                            invoice_lines = self.env['timesheet.invoice'].create({
                                    'analytic_account_id': proj.analytic_account_id.id,
                                    'invoicing_type_id': proj.invoicing_type_id.id,
                                    'invoice_start_date': month_start,
                                    'invoice_end_date': month_end,
                                    'hour_selection': proj.hour_selection,
                                    # 'custom_work_hours': str(custom_work_hours) + str(' Hours'),
                                    'custom_work_hours': proj.hour_selection + str(' Hours'),
                                    'rate_per_hour': proj.rate_per_hour,
                                    'min_bill': proj.total_rate,
                                    'worked_hours': sum_hours,
                                    'ideal_hours': ideal_time,
                                    'hours_charged': sum_hours if sum_hours > float(proj.hour_selection) else float(proj.hour_selection),
                                    'bill_amount': (sum_hours if sum_hours > float(proj.hour_selection) else float(proj.hour_selection)) * proj.rate_per_hour,
                                    'final_amount': (sum_hours if sum_hours > float(proj.hour_selection) else float(proj.hour_selection)) * proj.rate_per_hour,
                                    'holidays': len(holidays),
                                })
                            print "invoice_lines>>>>>>>>>>>", invoice_lines

        return True


    #This function is called when the MONTHLY ADVANCE scheduler run
    @api.multi
    def monthly_advance_invoice_scheduler_queue(self):

        def last_day_of_next_month(date):
            if date.month == 12:
                return date.replace(day=31)
            return date.replace(month=date.month+1, day=1) - datetime.timedelta(days=1)

        project_obj = self.search([])
        # print ">>>project_obj>>>>>>>>>>>>>", project_obj
        for project in  project_obj:
            # print ">>>>project >>>>", project, project.id
            analytic_lines = self.env['account.analytic.account'].search([('project_ids', '=', project.id)])
            # print "timesheet_inv_obj>>>>>>>>>>>>>", analytic_lines.mapped('project_ids')
            if analytic_lines:
                project_rec = analytic_lines.mapped('project_ids')
                if project_rec.invoicing_type_id.name == 'Monthly Advance':
                    for proj in project_rec:

                        #next month date logic
                        today1 = date.today()
                        d1 = today1 + relativedelta(months=1)
                        start_date = datetime.date(d1.year, d1.month, 1)
                        end_date = last_day_of_next_month(start_date)#datetime.date(date.year, date.month, calendar.mdays[date.month])
                        print "lllllllllllllllll", start_date, end_date


                        #previous month logic
                        today2 = date.today()
                        d2 = today2 - relativedelta(months=1)
                        date11 = date(d2.year, d2.month, 1)
                        date22 = date(today2.year, today2.month, 1) - relativedelta(days=1)
                        print ">>>>>>>>>>>>>>>>", date11
                        print "<<<<<<<<<<<<<<<<", date22


                        #This month logic
                        dt = datetime.datetime.now()
                        a = datetime.date(int(dt.year), int(dt.month), int(dt.day)).isocalendar()[1]
                        b = int(dt.year)
                        c = int(dt.month)
                        print "abc??????", b, c
                        month_start = datetime.date(int(dt.year), int(dt.month), 1)
                        month_end = self._last_day_of_month(datetime.date(int(dt.year), int(dt.month), int(dt.day)))
                        print "month_end,satrtdfuidhshfgvjkgvb", month_start, month_end


                        #Holiday Count Logic
                        holidays = self.env['public.holiday'].search([
                            ('public_holiday_date', '>=', month_start.strftime(DF)),
                            ('public_holiday_date', '<=', month_end.strftime(DF))])
                        print len(holidays)

                        # end

                        #WORKING DAYS LOGIC
                        start_date = month_start
                        end_date = month_end
                        days = end_date - start_date
                        valid_date_list = {(start_date + datetime.timedelta(days=x)).strftime('%d-%b-%Y')
                                                for x in range(days.days+1)
                                                if (start_date + datetime.timedelta(days=x)).isoweekday() <= 5
                                               }
                        working_days = len(valid_date_list)
                        print "Working Days",working_days


                        if len(holidays) >= 1.00:
                            daily_hours = float(proj.hour_selection) / working_days
                            holidays_hours = daily_hours * len(holidays)
                            custom_work_hours = round((float(proj.hour_selection) - holidays_hours),2)
                            print "IF>>>>>>custom_work_hours ADVANCE MONTHLY***************",daily_hours, holidays_hours
                        else:
                            print "else***************"
                            custom_work_hours = round(float(proj.hour_selection),2)
                            print "ELSE>>>>custom_work_hours ADVANCE MONTHLY***************", custom_work_hours


                        domain = [('project_id', '=', proj.id), ('active', '=', False)]
                        if month_start and month_end:
                            domain.extend([('date', '>=', date11.strftime(DF)), ('date', '<=', date22.strftime(DF))])
                        timesheet_lines = self.env['account.analytic.line'].search(domain)
                        # print "timesheet_lines>>>>>>>>", timesheet_lines
                        # print sum(timesheet_lines.mapped('unit_amount'))
                        sum_hours = sum(timesheet_lines.mapped('unit_amount'))

                        print "sum_hours@@@@@@@@@@", sum_hours, float(proj.hour_selection)

                        if sum_hours > float(proj.hour_selection):
                            print "if con got>>>>>>>>>>>>"
                            extra_hours = sum_hours - float(proj.hour_selection)
                            print "extra_hours>>>>>>>>>>>", extra_hours
                        else:
                            extra_hours = 0.00

                        total_charged = float(proj.hour_selection) + extra_hours

                        invoice_lines = self.env['timesheet.invoice'].create({
                                'analytic_account_id': proj.analytic_account_id.id,
                                'invoicing_type_id': proj.invoicing_type_id.id,
                                'invoice_start_date': month_start,
                                'invoice_end_date': month_end,
                                'hour_selection': proj.hour_selection,
                                # 'custom_work_hours': str(custom_work_hours) + str(' Hours'),
                                'custom_work_hours': proj.hour_selection + str(' Hours'),
                                'rate_per_hour': proj.rate_per_hour,
                                'min_bill': proj.total_rate,
                                'worked_hours': float(proj.hour_selection),
                                'ideal_hours': 0.00,
                                'additional_hours': extra_hours,
                                'hours_charged': total_charged,
                                'bill_amount': total_charged * proj.rate_per_hour,
                                'final_amount': total_charged * proj.rate_per_hour,
                                'holidays': len(holidays),
                            })

        return True


    #This function is called when the weekly Advance scheduler run
    @api.multi
    def weekly_advance_invoice_scheduler_queue(self):

        project_obj = self.search([])
        # print ">>>project_obj>>>>>>>>>>>>>", project_obj
        for project in  project_obj:
            # print ">>>>project >>>>", project, project.id
            analytic_lines = self.env['account.analytic.account'].search([('project_ids', '=', project.id)])
            # print "timesheet_inv_obj>>>>>>>>>>>>>", analytic_lines.mapped('project_ids')
            if analytic_lines:
                project_rec = analytic_lines.mapped('project_ids')
                if project_rec.invoicing_type_id.name == 'Weekly Advance':
                    for proj in project_rec:


                        #Previous Week DateRange Logic
                        prev_dates = []
                        today = date.today()
                        prev_monday = today - datetime.timedelta(days=today.weekday(), weeks=1)
                        prev_sunday = prev_monday - datetime.timedelta(days=1)
                        prev_saturday = prev_monday + datetime.timedelta(days=5)
                        print ">>>>>>>>days>>>>>>>>", today, prev_sunday, prev_monday, prev_saturday


                        #Current Week DateRange Logic
                        dt = datetime.datetime.now()
                        a = datetime.date(int(dt.year), int(dt.month), int(dt.day)).isocalendar()[1]
                        b = int(dt.year)
                        # print ">>>>>>>>A", a, b

                        date_in_between = self._CurrentweekBoundaries(int(b), int(a))
                        # print "date_in_between>>>>>>>>>>>", date_in_between
                        week_start = date_in_between[0]
                        week_end = date_in_between[1]
                        print "????????", week_start, week_end

                        #Holiday Count Logic
                        holidays = self.env['public.holiday'].search([
                            ('public_holiday_date', '>=', week_start.strftime(DF)),
                            ('public_holiday_date', '<=', week_end.strftime(DF))])
                        print len(holidays)


                        if len(holidays) >= 1.00:
                            daily_hours = float(proj.hour_selection) / 5
                            holidays_hours = daily_hours * len(holidays)
                            custom_work_hours = round((float(proj.hour_selection) - holidays_hours),2)
                            print "IF>>>>>>custom_work_hours***************",daily_hours, holidays_hours
                        else:
                            print "else***************"
                            custom_work_hours = round(float(proj.hour_selection),2)
                            print "ELSE>>>>custom_work_hours***************", custom_work_hours




                        domain = [('project_id', '=', proj.id), ('active', '=', False)]
                        if prev_sunday and prev_saturday:
                            domain.extend([('date', '>=', prev_sunday.strftime(DF)), ('date', '<=', prev_saturday.strftime(DF))])
                        timesheet_lines = self.env['account.analytic.line'].search(domain)
                        # print "timesheet_lines>>>>>>>>", timesheet_lines
                        # print sum(timesheet_lines.mapped('unit_amount'))
                        sum_hours = sum(timesheet_lines.mapped('unit_amount'))


                        if sum_hours > float(proj.hour_selection):
                            # print "if con got>>>>>>>>>>>>"
                            extra_hours = sum_hours - float(proj.hour_selection)
                            # print "extra_hours>>>>>>>>>>>", extra_hours
                        else:
                            extra_hours = 0.00

                        total_charged = custom_work_hours + extra_hours

                        invoice_lines = self.env['timesheet.invoice'].create({
                                'analytic_account_id': proj.analytic_account_id.id,
                                'invoicing_type_id': proj.invoicing_type_id.id,
                                'invoice_start_date': week_start,
                                'invoice_end_date': week_end,
                                'hour_selection': proj.hour_selection,
                                'custom_work_hours': str(int(custom_work_hours)) + str(' Hours'),
                                'rate_per_hour': proj.rate_per_hour,
                                'min_bill': custom_work_hours * proj.rate_per_hour,
                                # 'worked_hours': float(proj.hour_selection),
                                'worked_hours': custom_work_hours,
                                'ideal_hours': 0.00,
                                'additional_hours': extra_hours,
                                # 'hours_charged': sum_hours if sum_hours > custom_work_hours else custom_work_hours,
                                # 'bill_amount': (sum_hours if sum_hours > custom_work_hours else custom_work_hours) * proj.rate_per_hour,
                                # 'final_amount': (sum_hours if sum_hours > custom_work_hours else custom_work_hours) * proj.rate_per_hour,
                                'hours_charged': total_charged,
                                'bill_amount': total_charged * proj.rate_per_hour,
                                'final_amount': total_charged * proj.rate_per_hour,
                                'holidays': len(holidays),
                            })
                        # print "invoice_lines>>>>>>>>>>>", invoice_lines

        return True
