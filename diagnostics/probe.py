"""Read-only public HTTP audit. Cookie values stay in memory, never in the report."""
import hashlib
import http.cookiejar
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPCookieProcessor

ROOT = Path(__file__).resolve().parent
AGENTS = {
    'desktop': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36',
    'instagram_android': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/130.0.0.0 Mobile Safari/537.36 Instagram 354.0.0.0 Android',
    'instagram_ios': 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 354.0.0.0',
}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def probe(url, agent, jar=None, save=None):
    opener = build_opener(NoRedirect(), HTTPCookieProcessor(jar if jar is not None else http.cookiejar.CookieJar()))
    chain = []
    seen = set()
    for _ in range(10):
        if url in seen:
            chain.append({'error': 'redirect loop', 'url': url})
            break
        seen.add(url)
        try:
            try:
                response = opener.open(Request(url, headers={'User-Agent': AGENTS[agent]}), timeout=15)
            except HTTPError as error:
                response = error
            with response:
                body = response.read()
                headers = response.headers
                cookies = [value.split('=', 1)[0] + '=<redacted>' + (';' + value.split(';', 1)[1] if ';' in value else '') for value in headers.get_all('Set-Cookie', [])]
                item = {'url': url, 'status': response.code,
                        'headers': {key: value for key, value in headers.items() if key.lower() not in ('set-cookie',)},
                        'set_cookie': cookies, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}
                chain.append(item)
                if response.code in (301, 302, 303, 307, 308) and headers.get('Location'):
                    url = urljoin(url, headers['Location'])
                    continue
                if save:
                    sanitized = re.sub(rb'(name="csrf_token" value=")[^"]+', rb'\1<redacted>', body)
                    (ROOT / save).write_bytes(sanitized)
                break
        except Exception as error:
            chain.append({'url': url, 'error': str(error)})
            break
    return chain

if __name__ == '__main__':
    report = {'time_utc': datetime.now(timezone.utc).isoformat(), 'requests': []}
    for scheme in ('http', 'https'):
        for host in ('pobreestudante.com.br', 'www.pobreestudante.com.br'):
            for path in ('/', '/sistema', '/sistema/', '/sistema?utm_source=instagram&probe=a%2Fb', '/sistema/?utm_source=instagram&probe=a%2Fb'):
                url = f'{scheme}://{host}{path}'
                chain = probe(url, 'desktop')
                report['requests'].append({'agent': 'desktop', 'chain': chain})
                print(url, [(hop.get('status'), hop.get('headers', {}).get('Location'), hop.get('error')) for hop in chain], flush=True)
    for agent in AGENTS:
        for path, name in (('/', 'home'), ('/sistema/', 'system')):
            report['requests'].append({'agent': agent, 'chain': probe('https://pobreestudante.com.br' + path, agent, save=f'live-{name}-{agent}.html')})
    jar = http.cookiejar.CookieJar()
    report['session_reuse'] = [probe('https://pobreestudante.com.br/sistema/', 'desktop', jar) for _ in range(6)]
    report['routes'] = {path: probe('https://pobreestudante.com.br' + path, 'desktop') for path in (
        '/sistema/login', '/sistema/criar-usuario', '/sistema/recuperar-senha',
        '/sistema/static/css/styles.css', '/sistema/static/css/brand.css?v=20261031d',
        '/sistema/static/imagens/logo.png')}
    (ROOT / 'http-audit.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
