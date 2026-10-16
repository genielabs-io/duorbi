"""Versioned application payload inside A2A text; never sent to the model."""
import json


def encode_request(text, conversation=None):
    return json.dumps({'version': 1, 'intent': 'resume' if conversation else 'new',
                       'conversation_id': conversation, 'text': text}, ensure_ascii=False)


def decode_request(prompt):
    try:
        data = json.loads(prompt)
    except (ValueError, TypeError) as exc:
        raise ValueError('Use the duorbi launcher or its versioned request envelope') from exc
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('Unsupported Antigravity request envelope')
    text, intent, conversation = data.get('text'), data.get('intent'), data.get('conversation_id')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Request text is empty')
    if intent not in ('new', 'resume'):
        raise ValueError('Request intent must be new or resume')
    if intent == 'resume' and (not isinstance(conversation, str) or not conversation):
        raise ValueError('Resume requires the expected saved conversation ID')
    if intent == 'new' and conversation is not None:
        raise ValueError('A new request cannot carry a resume ID')
    return text, conversation
