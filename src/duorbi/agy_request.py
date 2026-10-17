"""Versioned application payload inside A2A text; never sent to the model."""
import json
import re


def validate_model(model):
    """Accept CLI slugs, not flags, labels or shell fragments; agy checks availability."""
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', model):
        raise ValueError('Model must be a CLI model ID from agy models (1-128 letters/digits/._-)')
    return model


def encode_request(text, conversation=None, *, model=None):
    data = {'version': 1, 'intent': 'resume' if conversation else 'new',
            'conversation_id': conversation, 'text': text}
    if model is not None:
        # Older servers reject v2, rather than silently ignoring a model choice.
        data.update(version=2, model=validate_model(model))
    return json.dumps(data, ensure_ascii=False)


def decode_request(prompt):
    try:
        data = json.loads(prompt)
    except (ValueError, TypeError) as exc:
        raise ValueError('Use the duorbi launcher or its versioned request envelope') from exc
    if (not isinstance(data, dict) or type(data.get('version')) is not int
            or data['version'] not in (1, 2)):
        raise ValueError('Unsupported Antigravity request envelope')
    model = None
    if data['version'] == 2:
        model = validate_model(data.get('model'))
    elif 'model' in data:
        raise ValueError('Model selection requires a version-2 request envelope')
    text, intent, conversation = data.get('text'), data.get('intent'), data.get('conversation_id')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Request text is empty')
    if intent not in ('new', 'resume'):
        raise ValueError('Request intent must be new or resume')
    if intent == 'resume' and (not isinstance(conversation, str) or not conversation):
        raise ValueError('Resume requires the expected saved conversation ID')
    if intent == 'new' and conversation is not None:
        raise ValueError('A new request cannot carry a resume ID')
    return text, conversation, model
