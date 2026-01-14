# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WorkflowTemplate(models.Model):
    _name = 'workflow.template'
    _description = 'Workflow Template'

    name = fields.Char('Template Name', required=True)
    model_name = fields.Char('Model', required=True, default='van_ban')
    description = fields.Text('Description')

    transition_ids = fields.One2many(
        'workflow.transition', 'template_id',
        string='Transitions'
    )

    active = fields.Boolean('Active', default=True)


class WorkflowTransition(models.Model):
    _name = 'workflow.transition'
    _description = 'Workflow Transition'

    template_id = fields.Many2one('workflow.template', string='Template', required=True, ondelete='cascade')
    name = fields.Char('Transition Name', required=True)
    from_state = fields.Char('From State', required=True)
    to_state = fields.Char('To State', required=True)

    # Conditions for transition
    condition_domain = fields.Char('Condition Domain', help='Domain expression for transition conditions')
    required_group = fields.Many2one('res.groups', string='Required Group')
    auto_transition = fields.Boolean('Auto Transition', help='Automatically execute this transition')

    # Actions to perform
    action_method = fields.Char('Action Method', help='Method to call on transition')
    email_template_id = fields.Many2one('mail.template', string='Email Template')

    sequence = fields.Integer('Sequence', default=10)
    active = fields.Boolean('Active', default=True)

    _order = 'sequence, id'

    def execute_transition(self):
        """Execute transition from transition record"""
        # Get van_ban record from context
        van_ban_id = self.env.context.get('van_ban_id')
        if not van_ban_id:
            raise UserError("No van_ban record specified")

        van_ban = self.env['van_ban'].browse(van_ban_id)
        if not van_ban.exists():
            raise UserError("Van ban record not found")

        return van_ban.execute_transition(self.id)


class VanBan(models.Model):
    _inherit = 'van_ban'

    # Override trang_thai to be dynamic
    workflow_template_id = fields.Many2one(
        'workflow.template',
        string='Workflow Template',
        help='Dynamic workflow template for this document'
    )

    # Dynamic states based on template
    available_transitions = fields.Many2many(
        'workflow.transition',
        compute='_compute_available_transitions',
        string='Available Transitions'
    )

    @api.depends('trang_thai', 'workflow_template_id')
    def _compute_available_transitions(self):
        """Compute available transitions based on current state and template"""
        for record in self:
            if record.workflow_template_id:
                transitions = self.env['workflow.transition'].search([
                    ('template_id', '=', record.workflow_template_id.id),
                    ('from_state', '=', record.trang_thai),
                    ('active', '=', True)
                ])
                record.available_transitions = transitions
            else:
                record.available_transitions = False

    def get_available_actions(self):
        """Get available actions based on workflow template"""
        self.ensure_one()
        actions = []

        for transition in self.available_transitions:
            # Check conditions
            if self._check_transition_conditions(transition):
                actions.append({
                    'name': transition.name,
                    'method': transition.action_method or f'action_{transition.to_state}',
                    'transition': transition,
                })

        return actions

    def _check_transition_conditions(self, transition):
        """Check if transition conditions are met"""
        # Check domain condition
        if transition.condition_domain:
            try:
                domain = eval(transition.condition_domain)
                if not self.search([('id', '=', self.id)] + domain):
                    return False
            except:
                return False

        # Check group permission
        if transition.required_group:
            if not self.env.user.has_group(transition.required_group.id):
                return False

        return True

    def execute_transition(self, transition_id):
        """Execute a workflow transition"""
        transition = self.env['workflow.transition'].browse(transition_id)
        if not transition or transition not in self.available_transitions:
            raise UserError("Invalid transition")

        # Update state
        old_state = self.trang_thai
        self.write({'trang_thai': transition.to_state})

        # Execute action method if specified
        if transition.action_method:
            method = getattr(self, transition.action_method, None)
            if method:
                method()

        # Send email if template specified
        if transition.email_template_id:
            transition.email_template_id.send_mail(self.id)

        # Log transition
        self._ghi_lich_su('trang_thai',
                         f'Transition: {old_state} -> {transition.to_state} ({transition.name})')

        return True

    # Override existing action methods to use dynamic workflow
    def action_gui_duyet(self):
        """Dynamic submit for approval"""
        if self.workflow_template_id:
            # Find transition for submit approval
            transition = self.available_transitions.filtered(
                lambda t: t.to_state == 'cho_duyet'
            )
            if transition:
                return self.execute_transition(transition.id)

        # Fallback to original logic
        return super().action_gui_duyet()

    def action_duyet(self):
        """Dynamic approve"""
        if self.workflow_template_id:
            transition = self.available_transitions.filtered(
                lambda t: t.to_state == 'da_duyet'
            )
            if transition:
                return self.execute_transition(transition.id)

        return super().action_duyet()

    def action_gui_ky(self):
        """Dynamic submit for signature"""
        if self.workflow_template_id:
            transition = self.available_transitions.filtered(
                lambda t: t.to_state == 'cho_ky'
            )
            if transition:
                return self.execute_transition(transition.id)

        return super().action_gui_ky()