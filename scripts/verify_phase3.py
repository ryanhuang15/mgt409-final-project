"""Offline evidence verification. Evaluation labels never enter application inputs."""
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from backend.app.config import PROJECT_ROOT, load_settings
from evaluation.evaluate import load_answer_key
from evaluation.evaluate_agents import score_result


def main():
    root = PROJECT_ROOT
    evidence = root / 'docs/evidence'
    live = json.loads((evidence / 'phase3-live-browser.json').read_text(encoding='utf-8'))
    score = score_result(live['result'], 'flawed', load_answer_key())
    settings = load_settings()
    files = [*list((root / 'frontend/dist').rglob('*')), *list(evidence.glob('phase3-*'))]
    secret_found = any(path.is_file() and settings.openai_api_key and settings.openai_api_key.encode() in path.read_bytes() for path in files)
    junit = ET.parse(root / 'runtime/pytest-phase3.xml').getroot()
    suites = list(junit.iter('testsuite'))
    python_tests = {name: sum(int(s.get(name, 0)) for s in suites) for name in ['tests','failures','errors','skipped']}
    browser = json.loads((root / 'runtime/playwright-results.json').read_text(encoding='utf-8'))
    summary = dict(verified_at=datetime.now(timezone.utc).isoformat(), python_tests=python_tests,
        browser_tests=browser['stats'], live_review=score,
        configuration=dict(selected_dotenv='project' if settings.env_file == root/'.env' else 'parent' if settings.env_file == root.parent/'.env' else 'none',
                           api_key_configured=settings.api_key_configured, secret_found_in_frontend_or_phase3_evidence=secret_found),
        limitations=['One fresh Phase 3 live scenario; clean/adversarial browser paths use labeled real Phase 2 runs.',
                     'Docker unavailable; image build and hosted smoke test not executed.',
                     'No external publication or purchase. No exact model billing provided.'])
    (evidence / 'phase3-verification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return score['passed'] and not secret_found and not python_tests['failures'] and not python_tests['errors'] and browser['stats']['unexpected'] == 0


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
