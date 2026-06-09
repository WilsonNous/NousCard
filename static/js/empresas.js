/**
 * empresas.js - Funcionalidades do formulário de empresas
 * NousCard
 */

document.addEventListener('DOMContentLoaded', function() {
    
    // ============================================================
    // Consultar CNPJ via BrasilAPI
    // ============================================================
    const btnConsultarCNPJ = document.getElementById('btnConsultarCNPJ');
    const campoDocumento = document.getElementById('documento');
    const campoSituacao = document.getElementById('situacaoCNPJ');
    
    if (btnConsultarCNPJ && campoDocumento) {
        btnConsultarCNPJ.addEventListener('click', async function() {
            const cnpj = campoDocumento.value.trim();
            if (!cnpj) {
                alert('Digite um CNPJ para consultar.');
                return;
            }
            
            btnConsultarCNPJ.disabled = true;
            btnConsultarCNPJ.textContent = 'Consultando...';
            
            try {
                const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
                
                const response = await fetch('/empresas/api/consultar-cnpj', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRF-Token': csrfToken
                    },
                    body: JSON.stringify({ cnpj: cnpj })
                });
                
                const data = await response.json();
                
                if (data.ok && data.dados) {
                    preencherCamposCNPJ(data.dados);
                    if (campoSituacao) {
                        campoSituacao.textContent = '✅ CNPJ encontrado';
                        campoSituacao.style.color = '#16a34a';
                    }
                } else {
                    if (campoSituacao) {
                        campoSituacao.textContent = '❌ ' + (data.message || 'CNPJ não encontrado');
                        campoSituacao.style.color = '#dc2626';
                    }
                    alert(data.message || 'CNPJ não encontrado');
                }
            } catch (error) {
                console.error('Erro ao consultar CNPJ:', error);
                alert('Erro ao consultar CNPJ. Tente novamente.');
            } finally {
                btnConsultarCNPJ.disabled = false;
                btnConsultarCNPJ.textContent = '🔍 Consultar CNPJ';
            }
        });
    }
    
    // ============================================================
    // Upload de Logo
    // ============================================================
    const inputLogo = document.getElementById('logoUpload');
    const previewLogo = document.getElementById('logoPreview');
    
    if (inputLogo) {
        inputLogo.addEventListener('change', async function() {
            const file = this.files[0];
            if (!file) return;
            
            // Preview local
            if (previewLogo) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    previewLogo.src = e.target.result;
                    previewLogo.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
            
            // Upload via API
            const empresaId = document.querySelector('input[name="empresa_id"]')?.value || 
                              window.location.pathname.split('/')[2];
            const csrfToken = document.querySelector('input[name="csrf_token"]')?.value || '';
            
            const formData = new FormData();
            formData.append('empresa_id', empresaId);
            formData.append('logo', file);
            
            try {
                const response = await fetch('/empresas/api/upload-logo', {
                    method: 'POST',
                    headers: {
                        'X-CSRF-Token': csrfToken
                    },
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.ok) {
                    // Atualizar preview com URL do servidor
                    if (previewLogo && data.logo_url) {
                        previewLogo.src = data.logo_url + '?t=' + new Date().getTime();
                    }
                    console.log('Logo atualizada:', data.logo_url);
                } else {
                    alert(data.message || 'Erro ao fazer upload da logo');
                }
            } catch (error) {
                console.error('Erro ao fazer upload:', error);
                // Só alerta se não for 501 (não implementado)
                if (!error.message?.includes('501')) {
                    alert('Erro ao fazer upload da logo.');
                }
            }
        });
    }
    
    // ============================================================
    // Máscara de CNPJ
    // ============================================================
    if (campoDocumento) {
        campoDocumento.addEventListener('input', function(e) {
            let value = this.value.replace(/\D/g, '');
            if (value.length > 14) value = value.slice(0, 14);
            
            if (value.length > 2) value = value.slice(0, 2) + '.' + value.slice(2);
            if (value.length > 6) value = value.slice(0, 6) + '.' + value.slice(6);
            if (value.length > 10) value = value.slice(0, 10) + '/' + value.slice(10);
            if (value.length > 15) value = value.slice(0, 15) + '-' + value.slice(15);
            
            this.value = value;
        });
    }
    
    // ============================================================
    // Confirmação de desativação
    // ============================================================
    const checkboxAtiva = document.getElementById('ativa');
    const confirmacaoDesativacao = document.getElementById('confirmarDesativacao');
    
    if (checkboxAtiva && confirmacaoDesativacao) {
        function toggleConfirmacao() {
            confirmacaoDesativacao.style.display = checkboxAtiva.checked ? 'none' : 'block';
        }
        
        checkboxAtiva.addEventListener('change', toggleConfirmacao);
        toggleConfirmacao(); // Estado inicial
    }
});

// ============================================================
// Preencher campos com dados do CNPJ
// ============================================================
function preencherCamposCNPJ(dados) {
    const mapa = {
        'nome': dados.razao_social || dados.nome_fantasia || '',
        'logradouro': dados.logradouro || '',
        'numero': dados.numero || '',
        'complemento': dados.complemento || '',
        'bairro': dados.bairro || '',
        'cep': dados.cep || '',
        'municipio': dados.municipio || '',
        'uf': dados.uf || '',
        'telefone': dados.telefone || '',
        'email': dados.email || ''
    };
    
    for (const [id, valor] of Object.entries(mapa)) {
        const campo = document.getElementById(id);
        if (campo && valor && !campo.value) {
            campo.value = valor;
        }
    }
}
