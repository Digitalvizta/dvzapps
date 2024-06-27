# -*- coding: utf-8 -*-


from odoo import api, fields, models, _
import string
from odoo.exceptions import ValidationError
import copy

class BtAssetMove(models.Model):
    _name = "bt.asset.move"
    _description = "Asset Move" 
    
    name = fields.Char(string='Name', default="New", copy=False)
    from_loc_id = fields.Many2one('bt.asset.location', string='From Location', required=True)
    asset_id = fields.Many2one('bt.asset', string='Asset', required=False, copy=False)
    to_loc_id = fields.Many2one('bt.asset.location', string='To Location', required=True)
    state = fields.Selection([
            ('draft', 'Draft'),
            ('done', 'Done')], string='State',track_visibility='onchange', default='draft', copy=False)
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('bt.asset.move') or 'New'
        result = super(BtAssetMove, self).create(vals)
        if vals.get('from_loc_id', False) or vals.get('to_loc_id', False):
            if result.from_loc_id == result.to_loc_id:
                raise ValidationError(_("From location and to location must be different."))
        if vals.get('asset_id',False):
            if result.asset_id.current_loc_id != result.from_loc_id:
                raise ValidationError(_("Current location and from location must be same while creating asset."))
        return result
     
    
    def write(self, vals):
        result = super(BtAssetMove, self).write(vals)
        if vals.get('from_loc_id', False) or vals.get('to_loc_id', False):
            for move in self:
                if move.from_loc_id == move.to_loc_id:
                    raise ValidationError(_("From location and to location must be different."))
        if vals.get('asset_id',False):
            for asset_obj in self:
                if asset_obj.asset_id.current_loc_id != asset_obj.from_loc_id:
                    raise ValidationError(_("Current location and from location must be same while creating asset."))
        return result
     
    def action_move(self):
        for move in self:
            move.asset_id.current_loc_id = move.to_loc_id and move.to_loc_id.id or False
            move.state = 'done'
        return True
    

