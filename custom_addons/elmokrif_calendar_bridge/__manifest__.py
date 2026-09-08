{
    "name": "EL MOKRIF Calendar Bridge",
    "summary": "Links appointments to chantiers, opportunities and controlled documents",
    "version": "17.0.1.0.0",
    "category": "Productivity/Calendar",
    "author": "EL MOKRIF",
    "license": "LGPL-3",
    "depends": ["calendar", "elmokrif_crm", "elmokrif_documents_bridge"],
    "data": [
        "security/calendar_rules.xml",
        "views/calendar_event_views.xml", "views/crm_lead_views.xml",
    ],
    "installable": True,
    "application": False,
}
