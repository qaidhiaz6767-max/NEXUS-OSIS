"""Invented fixtures for explicitly requested, temporary local demo sessions."""
from datetime import timedelta
from .validation import today_local


def seed_demo(registry):
    store = registry.store('osis')
    due = (today_local() + timedelta(days=3)).isoformat()
    fixtures = [
        ('create_project', {'title': 'Leadership workspace',
                            'goal': 'Clear plans, shared responsibilities and decisions ready for review.'}),
        ('create_task', {'title': 'Prepare the leadership briefing', 'owner': 'OSIS team',
                         'due_date': due, 'priority': 'high'}),
        ('create_task', {'title': 'Review the event timeline', 'owner': 'Planning team', 'due_date': due}),
        ('create_event', {'title': 'Weekly planning session', 'day': due, 'time': '14:00',
                          'location': 'Meeting room', 'details': 'Invented sample event for the demo.'}),
        ('remember', {'key': 'Meeting rhythm', 'value': 'Weekly planning session'}),
    ]
    for name, args in fixtures:
        item = store.propose(name, args)
        store.decide(item['id'], True)
    store.propose('create_task', {'title': 'Draft the weekly agenda', 'owner': 'Planning team', 'due_date': due})
