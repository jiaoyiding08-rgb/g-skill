"""Prewritten fixtures only. This provider never measures model quality."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[2]

def call_api(prompt, options, context):
    skill=context.get('vars',{}).get('skill')
    if skill not in ('g-ground','g-real','g-ship','g-review','g-repeat','g-lab'):
        return {'error':'Unknown fixture name'}
    return {'output':(ROOT/'examples'/f'{skill}.json').read_text(encoding='utf-8')}
