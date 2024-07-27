# -*- coding: utf-8 -*-
##############################################################################
{
    'name': 'Employee Sequence Id',
    'version': '1.0',
    'sequence': 1,
    'category': 'Human Resources',
    'description': """
        This module adds a unique Employee Sequence Number to the employee screen in Odoo.
        It provides a sequence number field for employees, enhancing tracking and identification.

        Key Features:
        - Displays a unique sequence number for each employee.
        - Customizes employee form and Kanban views to include the sequence number.
        - Provides a server action to generate sequence numbers for existing employees.
    """,
    'summary': 'Displays a unique sequence number Id for each employee in Odoo',
    'author': 'DigitalVizta',
    'website': 'https://digitalvizta.com/',
    'depends': ['hr'],
    'data': [
        'views/employee_sequence.xml',  # Customizations for employee form and Kanban views
        'views/employee_view.xml',  # Additional views for employee
        'data/ir_actions_server_data.xml',  # Server action definitions
        'data/action_generate_employee_sequences.xml'  # Data for action to generate sequences
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'images': ['static/description/odoo.png'],

    # Author and Support Details
    'pre_init_hook': 'pre_init_hook',  # Ensure to provide the pre-init hook function
    'post_init_hook': 'post_init_hook',  # Ensure to provide the post-init hook function
}
