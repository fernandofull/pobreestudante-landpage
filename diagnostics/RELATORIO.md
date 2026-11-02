# Investigação de acesso — 02/11/2026

Auditoria pública às 10:39 de Brasília. Mudanças apenas no checkout local; nada foi enviado à hospedagem. Link da bio a manter: **https://pobreestudante.com.br**.

## Conclusão sustentada pelas evidências

Há uma falha reproduzível no atendimento HTTP de `/sistema/`: retorna **503**, enquanto HTTPS retorna **200**, com e sem www. A inicial aceita HTTP sem redirecionar. Seu JavaScript publicado encaminha para `/sistema/` relativo, mantendo protocolo e host de origem. Assim, entrar pela inicial HTTP leva ao sistema que falha. Isso é uma cadeia de falha demonstrável; não prova que o Instagram tenha trocado o HTTPS do link da bio por HTTP. O motivo interno do 503 também permanece indeterminado sem logs.

O HTML publicado da inicial é idêntico ao arquivo local anterior às mudanças. Os quatro botões tinham `href="#"`, interceptação `preventDefault()` e `window.location.href = '/sistema/'`. Sem executar esse script, os botões não abrem o sistema. Não foi observado bloqueio de JavaScript pelo Instagram: trata-se de uma dependência desnecessária corrigida, não de uma causa confirmada nesse navegador.

## Respostas públicas e cadeias completas observadas

Cada linha abaixo vale para `pobreestudante.com.br` e `www.pobreestudante.com.br`.

| Protocolo e caminho | Cadeia observada |
| --- | --- |
| HTTP `/` | 200, sem Location |
| HTTPS `/` | 200, sem Location |
| HTTP `/sistema` | 301 → mesmo host HTTP `/sistema/` → 503 |
| HTTP `/sistema/` | 503, sem Location |
| HTTPS `/sistema` | 301 → mesmo host HTTPS `/sistema/` → 200 |
| HTTPS `/sistema/` | 200, sem Location |

Também testados `/sistema?utm_source=instagram&probe=a%2Fb` e `/sistema/?utm_source=instagram&probe=a%2Fb` nas quatro origens. O redirecionamento que acrescenta a barra preservou os parâmetros, inclusive `%2F`. Não houve loops nas cadeias testadas. Não existe atualmente redirecionamento público para HTTPS ou para retirar www.

Em HTTPS sem www, GET de `/sistema/login`, `/sistema/criar-usuario`, `/sistema/recuperar-senha`, dos dois CSS locais referenciados e da imagem do logo retornaram 200. O formulário aponta para POST `/sistema/login`, e os links e assets publicados mantêm o prefixo `/sistema/`. Não foram enviados formulários, criados usuários ou efetuado login; fluxos autenticados e possíveis loops após login não foram verificados. Dependências externas de CDN não foram auditadas.

Arquivo `http-audit.json`: URLs de cada salto, status, headers, tamanhos e hashes. Valores dos cookies foram suprimidos. Snapshots `live-*.html` representam o site publicado antes da implantação das correções; tokens CSRF estão suprimidos.

## Cookies e Flask

No GET HTTPS de `/sistema/`, o servidor emitiu:

```text
session=<redacted>; Secure; HttpOnly; Path=/; SameSite=Lax
```

- Domain ausente: cookie restrito ao host que o emitiu. Cookies de www e sem www ficam separados; padronizar o host evita essa divisão. Isso, sozinho, não prova perda de sessão no relato.
- Path `/`: abrange `/sistema/`; não há evidência de erro de escopo de caminho.
- Secure e HttpOnly presentes; SameSite=Lax. Não há evidência que justifique trocar por `None` ou retirar Secure. Lax é uma configuração documentada pelo Flask para navegação comum: https://flask.palletsprojects.com/en/stable/web-security/.
- Seis GET consecutivos com o mesmo cookie mantiveram exatamente o mesmo corpo/CSRF; apenas o primeiro emitiu Set-Cookie. Há evidência de aceitação da sessão nessa sequência curta, não de persistência da SECRET_KEY após restart, entre todos os workers ou no fluxo autenticado.
- O projeto fornecido contém somente HTML e imagens, sem app Flask, WSGI, configurações Python, `.env`, arquivos de servidor ou logs. Não foi possível auditar `SECRET_KEY`, `APPLICATION_ROOT`, `SCRIPT_NAME`, `PREFERRED_URL_SCHEME`, ProxyFix ou a configuração interna de cookies.

## Instagram

Foram enviados User-Agents de desktop, Instagram Android e Instagram iOS. Todos receberam 200 na inicial HTTPS e em `/sistema/`. A inicial foi idêntica byte a byte; o HTML do sistema foi idêntico após remover o token CSRF variável. Não apareceu bloqueio por esses User-Agents nas URLs testadas.

**Não foi testado o aplicativo Instagram real.** Alterar User-Agent não reproduz WebView/WKWebView, armazenamento de cookies, versão do app, rede do telefone, encaminhamento pela Meta, TLS do dispositivo ou execução de JavaScript. Não é possível declarar a incompatibilidade resolvida com este teste.

## Alterações locais

- `index.html`: quatro links nativos para `https://pobreestudante.com.br/sistema/`, sem dependência de JavaScript; removidos o interceptador e seu aviso sem uso. O script do QR Pix permanece.
- `sobre.html`: link de entrada também usa HTTPS sem www.
- `.htaccess`: regra de canonicalização 308 para HTTPS sem www, preservando o caminho e a query string original; destino fixo, sem refletir o Host recebido. O código 308 preserva método e corpo de requisições.
- `diagnostics/probe.py`: auditoria pública reproduzível com biblioteca padrão Python, somente GET, TLS validado, limite de saltos e detecção de loops. `python diagnostics/probe.py` atualiza as evidências e exige acesso de rede.

## Implantação e pendências na hospedagem

Verificações locais concluídas: parser HTML confirmou os quatro links da inicial e o link de `sobre.html` com destino HTTPS canônico, sem onclick/target; `node --check` aceitou o JavaScript restante; sintaxe Python e leitura do JSON válidas; snapshots do sistema com CSRF suprimido; `git diff --check` sem erros. Não foi realizado teste visual ou execução em navegador nesta sessão. A regra `.htaccess` foi revisada, mas não executada em LiteSpeed/Apache local.

1. Publicar os dois HTMLs. **Integrar**, no document root real, as regras do `.htaccess` antes das regras existentes de Python/Passenger/LSAPI; não substituir o arquivo da hospedagem, pois ele não foi fornecido. Não publicar a pasta `diagnostics` como conteúdo do site.
2. A regra fornecida pressupõe que `%{HTTPS}` reflete o TLS do visitante. Se TLS terminar em proxy/CDN e o backend receber HTTP, aplicá-la sem adaptação pode gerar loop. Nesse cenário, configurar a canonicalização no proxy de borda ou fazer o servidor normalizar o esquema somente a partir de proxies confiáveis. Não confiar indiscriminadamente em `X-Forwarded-Proto` enviado pelo cliente. O uso de ProxyFix depende da topologia real e do número de proxies: https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/.
3. Validar configuração/sintaxe no LiteSpeed real e repetir a auditoria após implantação. Para cada origem não canônica, esperar 308 para `https://pobreestudante.com.br` com o mesmo caminho e parâmetros. Para `/sistema` pode haver um segundo salto acrescentando `/`. A origem HTTPS canônica não deve redirecionar para si mesma. Testar também caminho percent-encoded e parâmetros repetidos, além do caso documentado nesta auditoria. Não há LiteSpeed instalado neste checkout para validar execução das regras.
4. Inspecionar os vhosts/listeners HTTP e HTTPS, document roots, handler/context de `/sistema/`, usuário do processo, virtualenv e comando de inicialização. A divergência 503/200 indica investigar diferenças entre os atendimentos; não identifica qual configuração é responsável.
5. Correlacionar access/error log do vhost, stderr da aplicação e logs de startup com as requisições HTTP que retornaram 503, em 02/11/2026 às 10:39 de Brasília (13:39 UTC). Procurar `set_env_vars.py`, `Traceback`, `Permission denied`, `No such file`, falhas de intérprete/venv e inicialização. Coletar o traceback completo e o caminho exato do script; conferir existência, proprietário/permissões, intérprete e origem da chamada. Não corrigir permissões amplamente nem editar esse script sem identificar o erro. A documentação de administração do LiteSpeed oferece os pontos de diagnóstico: https://docs.litespeedtech.com/lsws/cp/cpanel/.
6. **Nenhum log de `set_env_vars.py` foi disponibilizado ou acessado. Não existe evidência nesta auditoria que atribua o 503 a esse arquivo.** Não houve acesso SSH, painel ou credenciais de hospedagem na sessão.
7. No Flask real, conferir chave secreta estável fornecida por configuração persistente, igual em todos os workers, sem geração a cada import/restart. Reiniciar de forma controlada e confirmar que uma sessão de teste continua válida sem expor a chave. Conferir esquema HTTPS reconhecido pela aplicação e URLs geradas. Não adicionar ProxyFix automaticamente. Referência: https://flask.palletsprojects.com/en/stable/config/.
8. Após publicação, usar conta de teste para login, navegação autenticada, refresh e recuperação de sessão no Instagram Android/iOS real e em navegador externo. Registrar URL final, versão do app/SO, horário e falha observada. Manter o link da bio na raiz HTTPS sem www; conferir seu valor no perfil, que não foi acessado nesta sessão.

Não houve implantação nem validação no servidor das correções locais. O problema específico no navegador interno do Instagram permanece sem reprodução direta; a falha HTTP do sistema foi comprovada e o caminho de entrada foi corrigido localmente.
