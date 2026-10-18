"""The cost types used everywhere in job costing."""

COST_TYPES = [
    ('material', 'Material'),
    ('labour', 'Labour'),
    ('equipment', 'Equipment'),
    ('subcontract', 'Subcontract'),
    ('site_overhead', 'Site Overheads'),
    ('ho_overhead', 'Head-Office Overheads'),
    ('other', 'Other / Not Split'),
]
# Direct cost = everything charged to the job itself (all except head-office overheads).
DIRECT_TYPES = ('material', 'labour', 'equipment', 'subcontract', 'site_overhead', 'other')
# BOQ budget split fields, per unit of the BOQ item.
SPLIT_FIELDS = {
    'material': 'cost_material_unit',
    'labour': 'cost_labour_unit',
    'equipment': 'cost_equipment_unit',
    'subcontract': 'cost_subcontract_unit',
    'site_overhead': 'cost_overhead_unit',
}
# Cost types a product, category or account can be set to (head-office overheads come from allocations,
# but an account can also be marked as head-office overhead).
PRODUCT_COST_TYPES = [t for t in COST_TYPES if t[0] != 'other']
