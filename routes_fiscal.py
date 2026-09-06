# ================================
# MÓDULO FISCAL / LALUR
# ================================

from flask import request, jsonify
import csv
import io
from decimal import Decimal, getcontext

# Ajuste de precisão para cálculos financeiros
getcontext().prec = 10

def classificar_transacao(descricao, categoria, valor):
    """
    Classifica a transação nos grupos:
    - RECEITAS: Faturamento de Locações, Venda de Veículos (tratado separadamente), outras receitas.
    - DESPESAS_DEDUTIVEIS: Manutenção, Seguros, IPVA, Salários, etc.
    - MULTAS_TRANSITO: multas de trânsito (serão ajustadas no LALUR)
    """
    desc = descricao.lower() if descricao else ''
    cat = categoria.lower() if categoria else ''

    # Mapeamento de categorias do financeiro para grupos
    if cat in ['receitas de vendas', 'reembolso multas', 'reembolso pedágio', 
               'reembolso lavagem', 'reembolso combustível', 'outros reembolsos',
               'rendimentos', 'antecipação', 'reembolso avarias']:
        return 'RECEITA'

    # Despesas dedutíveis (exceto multas)
    if 'multa' in desc or 'multa' in cat:
        return 'MULTA_TRANSITO'

    # Despesas operacionais (manutenção, peças, seguros, IPVA, salários, etc.)
    if any(palavra in desc for palavra in ['manut', 'oficina', 'pecas', 'seguro', 'ipva', 
                                            'licenciamento', 'salario', 'folha', 'proventos',
                                            'combustivel', 'pedagio', 'lavagem', 'estacionamento',
                                            'despachante', 'diaria', 'telefone', 'internet',
                                            'energia', 'aluguel', 'imposto', 'taxa', 'tarifa',
                                            'consorcio', 'financiamento', 'emprestimo']):
        return 'DESPESA_DEDUTIVEL'

    # Se não encaixar, classifica como DESPESA_DEDUTIVEL por padrão (ajustável)
    # Mas vamos considerar que tudo que é saída é despesa dedutível a menos que seja multa
    if valor < 0:
        return 'DESPESA_DEDUTIVEL'

    return 'OUTROS'

def consolidar_fiscal(transacoes, depreciacao_periodo, venda_veiculos_valor, venda_veiculos_custo, multas_transito_extra=0):
    """
    Processa as transações e calcula:
    - Ganho de Capital
    - Lucro Líquido Contábil
    - Base de Cálculo do Lucro Real (com ajuste de multas)
    - CSLL, IRPJ Normal e Adicional
    """
    receitas = Decimal(0)
    despesas_dedutiveis = Decimal(0)
    multas_transito = Decimal(multas_transito_extra)

    for t in transacoes:
        valor = Decimal(str(t.get('valor', 0)))
        desc = t.get('descricao', '')
        cat = t.get('categoria', '')
        tipo = t.get('tipo', '')  # 'Entrada' ou 'Saída' (do financeiro)

        # Se for entrada, é receita, exceto se for venda de veículo (tratado separadamente)
        if tipo == 'Entrada' or valor > 0:
            # Verifica se é venda de veículo (pode ser por descrição)
            if 'venda' in desc.lower() and ('veiculo' in desc.lower() or 'frota' in desc.lower()):
                # Será tratado no ganho de capital, não soma como receita operacional
                continue
            # Caso contrário, é receita operacional (locação, reembolsos, etc.)
            receitas += valor
        else:
            # Saída
            classificacao = classificar_transacao(desc, cat, valor)
            if classificacao == 'MULTA_TRANSITO':
                multas_transito += abs(valor)
            elif classificacao == 'DESPESA_DEDUTIVEL':
                despesas_dedutiveis += abs(valor)
            # Outros (como despesas não dedutíveis) podem ser ignorados ou adicionados como ajuste

    # Ganho de Capital
    ganho_capital = Decimal(venda_veiculos_valor) - Decimal(venda_veiculos_custo)

    # Resultado Contábil (Lucro Líquido)
    lucro_liquido = receitas + ganho_capital - despesas_dedutiveis - Decimal(depreciacao_periodo)

    # Base LALUR (adição de multas)
    base_lalur = lucro_liquido + multas_transito

    # Cálculo dos impostos
    csll = base_lalur * Decimal('0.09')
    irpj_normal = base_lalur * Decimal('0.15')
    # Adicional: limite trimestral R$ 60.000 (considerando que o período é trimestral)
    # Se o período for mensal, ajustar. Vou assumir trimestral.
    limite_trimestral = Decimal('60000')
    excedente = max(base_lalur - limite_trimestral, Decimal(0))
    irpj_adicional = excedente * Decimal('0.10')

    return {
        'receitas_operacionais': float(receitas),
        'ganho_capital': float(ganho_capital),
        'despesas_dedutiveis': float(despesas_dedutiveis),
        'depreciacao_periodo': float(depreciacao_periodo),
        'multas_transito_pagas': float(multas_transito),
        'lucro_liquido_contabil': float(lucro_liquido),
        'base_lalur': float(base_lalur),
        'csll': float(csll),
        'irpj_normal': float(irpj_normal),
        'irpj_adicional': float(irpj_adicional),
        'irpj_total': float(irpj_normal + irpj_adicional),
        'carga_tributaria': float(csll + irpj_normal + irpj_adicional)
    }

# ===== NOVO ENDPOINT =====
@app.route('/api/consolidar_fiscal', methods=['POST'])
def consolidar_fiscal_endpoint():
    """
    Recebe um CSV (ou JSON) com as transações e os parâmetros adicionais.
    Espera:
    - file: arquivo CSV (opcional, se não enviar, usar 'transacoes' no JSON)
    - depreciacao: número
    - venda_valor: número
    - venda_custo: número
    - multas_extra: número (opcional)
    """
    data = request.get_json()
    if not data:
        return jsonify({'erro': 'Dados não enviados'}), 400

    # Pode vir como CSV ou como array de transações
    transacoes = data.get('transacoes', [])
    if not transacoes and 'file' in request.files:
        file = request.files['file']
        if file.filename.endswith('.csv'):
            stream = io.StringIO(file.stream.read().decode('utf-8'))
            reader = csv.DictReader(stream, delimiter=';')
            transacoes = []
            for row in reader:
                # Converte valor (substitui vírgula por ponto)
                val_str = row.get('Valor', '0').replace('.', '').replace(',', '.')
                try:
                    valor = float(val_str)
                except:
                    valor = 0.0
                transacoes.append({
                    'descricao': row.get('Descrição', ''),
                    'categoria': row.get('Categoria', ''),
                    'tipo': row.get('Tipo', ''),
                    'valor': valor
                })

    if not transacoes:
        return jsonify({'erro': 'Nenhuma transação fornecida'}), 400

    # Parâmetros
    depreciacao = float(data.get('depreciacao', 0))
    venda_valor = float(data.get('venda_valor', 0))
    venda_custo = float(data.get('venda_custo', 0))
    multas_extra = float(data.get('multas_extra', 0))

    resultado = consolidar_fiscal(transacoes, depreciacao, venda_valor, venda_custo, multas_extra)
    return jsonify(resultado)