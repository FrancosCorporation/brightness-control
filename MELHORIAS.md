# Melhorias do Brightness Control

## 0. Como usar

- Execute os itens na ordem P0 → P1 → P2 → P3.
- Marque cada item como concluído após sua verificação.
- Não execute a suíte de testes sem solicitação.

## 1. Diagnóstico executivo

Aplicação desktop GTK para Linux que controla brilho físico por DDC/CI e escurecimento por XRandR. O fluxo principal está implementado e já tem testes e CI, mas o status dos comandos externos não é respeitado, configurações malformadas podem causar exceções e o README aponta para uma execução Docker sem arquivos de container.

## 2. Tabela de prioridades

| Prioridade | Itens | Estado |
|---|---|---|
| P0 | — | Nenhum item identificado |
| P1 | BUG-01 | Concluído |
| P2 | BUG-02, BUG-03 | Concluídos |
| P2 | DEVOPS-01 | Planejado |
| P3 | DOC-01 | Concluído |

## 3. Segurança

Nenhum segredo ou credencial foi encontrado nos arquivos rastreados nesta inspeção.

## 4. Bugs

### BUG-01 · Respeitar falhas de `ddcutil` e `xrandr` [P1]

- **Arquivo:** `brightness-gui:39-54,147-202,204-283,480-688`
- **Evidência:** os setters tratam qualquer processo iniciado como sucesso sem conferir `returncode`; as ações de toggle, restauração e UI também ignoram falhas e podem informar sucesso ou deixar de restaurar o valor original.
- **Mudança:** verificar o código de saída dos comandos de leitura e escrita, propagar falhas pelas ações CLI e manter erros separados por operação na interface; manter a janela aberta se confirmar ou restaurar não for possível.
- **Aceite:** nenhuma ação informa sucesso nem persiste um novo valor quando algum comando necessário falha; uma mensagem não apaga a falha da outra modalidade; Cancelar/fechar só conclui depois de restaurar os valores que foram lidos.
- **Verificação:** `python3 -m py_compile brightness-gui`; revisar os ramos de retorno dos setters, ações CLI, workers, confirmação e cancelamento.
- **Estado:** [x] concluído.

### BUG-02 · Validar valores salvos antes de usá-los [P2]

- **Arquivo:** `brightness-gui:102-119,126-137,247-253,271-312`
- **Evidência:** JSON válido com valor não numérico, booleano ou não finito em `hw`, `sw` ou `sw_toggle` pode causar exceção ou uma decisão incorreta ao iniciar a interface e os atalhos.
- **Mudança:** normalizar valores numéricos finitos dentro dos limites e usar defaults para tipos ou valores inválidos.
- **Aceite:** configurações com valores inválidos não interrompem a inicialização e os valores efetivos permanecem dentro dos limites de hardware/software.
- **Verificação:** `python3 -m py_compile brightness-gui`; revisar os conversores e os caminhos que leem `hw`, `sw` e `sw_toggle`.
- **Estado:** [x] concluído.

### BUG-03 · Gravar configuração sem truncamento [P2]

- **Arquivo:** `brightness-gui:141-166`
- **Evidência:** salvar abre o arquivo final diretamente com modo `w`; interrupção durante a gravação pode deixar JSON incompleto, e erros de disco são ignorados.
- **Mudança:** escrever arquivo temporário no mesmo diretório, sincronizar e substituir atomicamente; retornar sucesso/falha aos chamadores e limitar as permissões do arquivo.
- **Aceite:** a configuração anterior permanece intacta se uma gravação falhar; os chamadores recebem o resultado real da persistência.
- **Verificação:** `python3 -m py_compile brightness-gui`; revisar o uso de arquivo temporário, `fsync`, substituição atômica e retorno booleano.
- **Estado:** [x] concluído.

## 5. Qualidade e experiência

O status acessível dos comandos e da restauração está coberto por BUG-01.

## 6. DevOps

### DEVOPS-01 · Reduzir permissões do workflow [P2]

- **Arquivo:** `.github/workflows/ci.yml:1-19`
- **Evidência:** o workflow não declara permissões mínimas para o token padrão do GitHub Actions.
- **Mudança:** limitar as permissões do workflow a leitura de conteúdo.
- **Aceite:** checkout e CI continuam com `contents: read` e sem permissões de escrita implícitas.
- **Verificação:** `git diff --check`; revisar o bloco `permissions` e os jobs do workflow.
- **Estado:** [ ] planejado.

## 7. Documentação

### DOC-01 · Corrigir o fluxo de instalação [P3]

- **Arquivo:** `README.md:3,37-68`
- **Evidência:** a seção inicial recomenda `docker compose up --build`, mas o repositório não contém Dockerfile nem arquivo Compose; a frase seguinte contradiz a recomendação.
- **Mudança:** documentar a instalação Linux local como fluxo suportado e listar os pacotes necessários para DDC/CI e XRandR.
- **Aceite:** os comandos documentados correspondem aos arquivos presentes e instalam as dependências citadas pelo app.
- **Verificação:** `git diff --check`; conferir comandos por distribuição com a lista de dependências e o executável `brightness-gui`.
- **Estado:** [x] concluído.

## 8. Ordem de execução

1. BUG-01 (P1).
2. BUG-02 e BUG-03 (P2); DEVOPS-01 aguarda o escopo OAuth `workflow` para entrar na branch remota.
3. DOC-01 (P3).

## 9. Fora de escopo

- Executar testes existentes, iniciar GUI ou interagir com monitor físico.
- Adicionar suporte Wayland, distribuir pacotes ou criar infraestrutura Docker para uma aplicação que depende do desktop X11/GTK.
- Alterar a UI para definir perfis independentes por monitor.

## 10. Definição de pronto

- Os itens aplicáveis à branch de revisão estão verificados estaticamente; DEVOPS-01 está pendente nela porque o GitHub recusou o commit de workflow sem o escopo OAuth `workflow`.
- A sintaxe Python compila; README e workflow correspondem ao repositório.
- As alterações estão commitadas e enviadas à branch atual.
