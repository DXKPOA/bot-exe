const state = {
  games: window.__INITIAL_DATA__.games || [],
  categories: window.__INITIAL_DATA__.categories || [],
  profiles: window.__INITIAL_DATA__.profiles || [],
  reviews: window.__INITIAL_DATA__.reviews || [],
  filters: { q: '', category_id: '', sort: 'popular' },
};

const dom = {
  grid: document.getElementById('catalogGrid'),
  meta: document.getElementById('catalogMeta'),
  search: document.getElementById('searchInput'),
  category: document.getElementById('categorySelect'),
  sort: document.getElementById('sortSelect'),
  modal: document.getElementById('gameModal'),
  modalContent: document.getElementById('modalContent'),
  prompt: document.getElementById('promptInput'),
  model: document.getElementById('modelInput'),
  scenario: document.getElementById('scenarioSelect'),
  output: document.getElementById('aiOutput'),
  outputStatus: document.getElementById('outputStatus'),
  runAiBtn: document.getElementById('runAiBtn'),
  healthBtn: document.getElementById('healthBtn'),
};

const scenarioConfig = {
  chat: {
    hint: 'Ты консультант магазина. Ответь кратко, списком и с итоговой рекомендацией.',
    prompt: 'Ответь как консультант магазина: что выбрать на PS5 до 2500 рублей?'
  },
  search: {
    hint: 'Найди подходящие игры по критериям. Верни 3-5 вариантов и короткое сравнение.',
    prompt: 'Найди кооперативную игру на PC до 2500 рублей с высоким рейтингом.'
  },
  recommend: {
    hint: 'Сделай персональные рекомендации по данным профилей и покупок.',
    prompt: 'Порекомендуй 3 игры пользователю, который любит RPG и игры с высоким рейтингом.'
  },
  summary: {
    hint: 'Сделай короткую сводку отзывов: плюсы, минусы, вывод.',
    prompt: 'Сделай краткую сводку отзывов: что чаще всего нравится и что критикуют пользователи.'
  }
};

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderInline(line) {
  const escaped = escapeHtml(line);
  return escaped
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/__(.+?)__/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function renderAiMarkdown(text) {
  const lines = String(text || '').replace(/\r/g, '').split('\n');
  let html = '';
  let inList = false;

  for (const raw of lines) {
    const line = raw.trim();

    if (!line) {
      if (inList) {
        html += '</ul>';
        inList = false;
      }
      continue;
    }

    const headingMatch = line.match(/^#{1,6}\s+(.+)$/);
    if (headingMatch) {
      if (inList) {
        html += '</ul>';
        inList = false;
      }
      html += `<h4>${renderInline(headingMatch[1])}</h4>`;
      continue;
    }

    const listMatch = line.match(/^[-*]\s+(.+)$/);
    if (listMatch) {
      if (!inList) {
        html += '<ul>';
        inList = true;
      }
      html += `<li>${renderInline(listMatch[1])}</li>`;
      continue;
    }

    if (inList) {
      html += '</ul>';
      inList = false;
    }
    html += `<p>${renderInline(line)}</p>`;
  }

  if (inList) {
    html += '</ul>';
  }

  return html || '<p>Пустой ответ модели.</p>';
}

function setOutputHtml(html) {
  dom.output.innerHTML = html;
}

function setOutputText(text) {
  dom.output.textContent = text;
}

function buildScenarioPrompt(scenario, userPrompt) {
  const cfg = scenarioConfig[scenario] || scenarioConfig.chat;
  return `${cfg.hint}\n\nЗадача пользователя:\n${userPrompt}`;
}

function formatPrice(value) {
  return `${Number(value || 0).toLocaleString('ru-RU')} ₽`;
}

function cardTemplate(game) {
  return `
    <article class="game-card card">
      <div class="game-card__cover" style="--cover:${game.cover}">
        <span class="badge">${game.category_name}</span>
      </div>
      <div class="game-card__body">
        <div class="meta-row"><span>${game.developer_name}</span><span>${game.release_year}</span></div>
        <h3 class="game-card__title">${game.title}</h3>
        <p class="game-card__desc">${game.short_description}</p>
        <div class="chips">
          <span class="chip">⭐ ${game.review_avg}</span>
          <span class="chip">${game.platforms || 'Платформа не указана'}</span>
          <span class="chip">${game.review_count} отзывов</span>
        </div>
        <div class="price-row">
          <div>
            <div class="price">${formatPrice(game.price)}</div>
            <div class="stock ${game.in_stock ? '' : 'stock--off'}">${game.in_stock ? 'В наличии' : 'Нет в наличии'}</div>
          </div>
          <button class="btn btn--secondary" data-open-game="${game.id}">Подробнее</button>
        </div>
      </div>
    </article>`;
}

function renderCatalog(items = state.games) {
  if (!items.length) {
    dom.meta.innerHTML = `<span>Найдено 0 позиций</span>`;
    dom.grid.innerHTML = `<div class="empty-state">По этим параметрам ничего не найдено. Попробуйте изменить запрос, категорию или сортировку.</div>`;
    return;
  }

  dom.meta.innerHTML = `<span>Найдено <strong>${items.length}</strong> игр</span><span>Актуальная выборка по фильтрам</span>`;
  dom.grid.innerHTML = items.map(cardTemplate).join('');
}

async function fetchCatalog() {
  const params = new URLSearchParams();
  if (state.filters.q) params.set('q', state.filters.q);
  if (state.filters.category_id) params.set('category_id', state.filters.category_id);
  if (state.filters.sort) params.set('sort', state.filters.sort);

  const response = await fetch(`/api/catalog?${params.toString()}`);
  const payload = await response.json();
  renderCatalog(payload.items || []);
}

async function openGame(gameId) {
  const response = await fetch(`/api/game/${gameId}`);
  const payload = await response.json();
  if (!response.ok) {
    alert(payload.error || 'Не удалось открыть карточку игры.');
    return;
  }
  const { game, reviews, similar } = payload;
  dom.modalContent.innerHTML = `
    <div class="modal-layout">
      <div class="modal-side">
        <div class="modal-cover" style="--cover:${game.cover}">
          <span class="badge">${game.category_name}</span>
        </div>
        <div class="modal-info">
          <div><strong>Разработчик:</strong> ${game.developer_name}</div>
          <div><strong>Платформы:</strong> ${game.platforms}</div>
          <div><strong>Дата выхода:</strong> ${game.release_date || '—'}</div>
          <div><strong>Рейтинг:</strong> ${game.review_avg}</div>
          <div><strong>Цена:</strong> ${formatPrice(game.price)}</div>
          <div><strong>Статус:</strong> ${game.in_stock ? 'В наличии' : 'Нет в наличии'}</div>
        </div>
      </div>
      <div class="modal-main">
        <div>
          <div class="meta-row"><span>${game.category_name}</span><span>${game.review_count} отзывов</span></div>
          <h2 style="margin:10px 0 0;font-size:2rem">${game.title}</h2>
          <p style="margin:14px 0 0;color:var(--muted);line-height:1.72">${game.description}</p>
        </div>
        <div class="modal-info">
          <strong>Что пишут игроки</strong>
          ${reviews.length ? reviews.map(r => `
            <div class="modal-review">
              <strong>${r.username} · ${r.rating}/10</strong>
              <p>${r.text}</p>
            </div>`).join('') : '<div class="empty-state">Пока нет отзывов по этой игре.</div>'}
        </div>
        <div class="modal-info">
          <strong>Похожие игры</strong>
          <div class="chips">${similar.length ? similar.map(item => `<span class="chip">${item.title}</span>`).join('') : '<span class="chip">Похожих игр не найдено</span>'}</div>
        </div>
      </div>
    </div>`;
  dom.modal.classList.remove('hidden');
  dom.modal.setAttribute('aria-hidden', 'false');
}

function closeModal() {
  dom.modal.classList.add('hidden');
  dom.modal.setAttribute('aria-hidden', 'true');
}

async function runAi() {
  const prompt = dom.prompt.value.trim();
  const model = dom.model.value.trim();
  const scenario = dom.scenario.value;
  if (!prompt) {
    dom.outputStatus.textContent = 'ошибка';
    setOutputText('Введите запрос для модели.');
    return;
  }

  const preparedPrompt = buildScenarioPrompt(scenario, prompt);

  dom.outputStatus.textContent = 'выполняется';
  setOutputText('Отправляем запрос в backend...');
  dom.runAiBtn.disabled = true;

  try {
    const response = await fetch('/api/ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: preparedPrompt, model, scenario }),
    });
    const payload = await response.json();
    if (!response.ok) {
      dom.outputStatus.textContent = 'ошибка';
      setOutputText(payload.error || payload.raw || 'Неизвестная ошибка.');
      return;
    }
    dom.outputStatus.textContent = `${payload.model} · ${payload.scenario}`;
    setOutputHtml(renderAiMarkdown(payload.answer || 'Модель не вернула текст ответа.'));
  } catch (error) {
    dom.outputStatus.textContent = 'сбой сети';
    setOutputText(`Ошибка при обращении к backend: ${error.message}`);
  } finally {
    dom.runAiBtn.disabled = false;
  }
}

async function checkHealth() {
  dom.outputStatus.textContent = 'проверка';
  setOutputText('Проверяем backend...');
  try {
    const response = await fetch('/health');
    const payload = await response.json();
    dom.outputStatus.textContent = 'backend ok';
    setOutputHtml(`<pre>${escapeHtml(JSON.stringify(payload, null, 2))}</pre>`);
  } catch (error) {
    dom.outputStatus.textContent = 'ошибка';
    setOutputText(`Backend недоступен: ${error.message}`);
  }
}

function applyScenario(scenario) {
  const cfg = scenarioConfig[scenario] || scenarioConfig.chat;
  dom.scenario.value = scenario;
  dom.prompt.value = cfg.prompt;
}

function initEvents() {
  dom.search.addEventListener('input', (e) => {
    state.filters.q = e.target.value.trim();
    fetchCatalog();
  });

  dom.category.addEventListener('change', (e) => {
    state.filters.category_id = e.target.value;
    fetchCatalog();
  });

  dom.sort.addEventListener('change', (e) => {
    state.filters.sort = e.target.value;
    fetchCatalog();
  });

  dom.grid.addEventListener('click', (e) => {
    const button = e.target.closest('[data-open-game]');
    if (button) openGame(button.dataset.openGame);
  });

  document.querySelectorAll('[data-close-modal]').forEach(el => el.addEventListener('click', closeModal));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeModal();
  });

  dom.runAiBtn.addEventListener('click', runAi);
  dom.healthBtn.addEventListener('click', checkHealth);

  dom.scenario.addEventListener('change', () => {
    applyScenario(dom.scenario.value);
    document.querySelectorAll('.scenario-pill').forEach(x => {
      x.classList.toggle('is-active', x.dataset.scenario === dom.scenario.value);
    });
  });

  document.querySelectorAll('.scenario-pill').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.scenario-pill').forEach(x => x.classList.remove('is-active'));
      btn.classList.add('is-active');
      applyScenario(btn.dataset.scenario);
    });
  });
}

renderCatalog(state.games);
initEvents();
applyScenario(dom.scenario.value);
