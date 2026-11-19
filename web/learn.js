// ===================== Штурман 38 · раздел «Учёба» =====================
// Разметка, светофоры и регулировщик, памятка при ДТП, зима в Иркутске, тренировка дня.
(function () {
const W = '#ffffff', BLK = '#1b1b1b', RED = '#d6282b', YEL = '#f2c200', GRN = '#1e9e4a', AMB = '#eb9d2a', ASPH = '#5d5f57', OFF = '#3a3b36';
const el = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const T = (x, y, sz, str, c, wt) => `<text x="${x}" y="${y}" text-anchor="middle" font-family="Arial,sans-serif" font-weight="${wt || 700}" font-size="${sz}" fill="${c}">${str}</text>`;
const ln = (d, c, w, extra) => `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="butt" ${extra || ''}/>`;
const head = (x, y, deg, s, c) => { const r = deg * Math.PI / 180, dx = Math.cos(r), dy = Math.sin(r), bx = x - s * dx, by = y - s * dy, k = s * .72;
  return `<polygon points="${x},${y} ${bx - k * dy},${by + k * dx} ${bx + k * dy},${by - k * dx}" fill="${c}"/>`; };
const svg = (inner, size) => `<svg viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${inner}</svg>`;

// ---------- рисунки: разметка ----------
const road = s => `<rect x="2" y="2" width="96" height="96" rx="6" fill="${ASPH}"/>${s || ''}`;
const carTop = (x, y, c, up) => `<rect x="${x - 7}" y="${y - 11}" width="14" height="22" rx="4" fill="${c}"/><rect x="${x - 5}" y="${up ? y - 7 : y + 1}" width="10" height="6" rx="1.5" fill="#2b2d33" opacity=".8"/>`;
const vl = (x, c, dash, w) => ln(`M${x} 2 V98`, c || W, w || 3, dash ? `stroke-dasharray="${dash}"` : '');
const curb = (x) => `<rect x="${x}" y="2" width="${98 - x}" height="96" fill="#b9b6a6"/><rect x="${x}" y="2" width="3" height="96" fill="#8f8c7d"/>`;
const arrowUp = (x, y, c) => ln(`M${x} ${y + 18} V${y + 6}`, c, 4) + head(x, y, -90, 7, c);

const MARK = [
  { n: '1.1', name: 'Сплошная линия', short: 'Сплошная', pic: road(vl(50) + carTop(70, 64, AMB, true) + carTop(30, 34, '#9aa', false)),
    what: 'Разделяет встречные потоки или полосы в опасных местах.', todo: 'Пересекать её и наезжать на неё нельзя.',
    trap: 'Объехать пробку или обогнать через сплошную по встречке — за это лишают прав.', memo: 'Сплошная — как стена: через неё не перелезаем.' },
  { n: '1.2', name: 'Линия края проезжей части', short: 'Край дороги', pic: road(`<rect x="80" y="2" width="18" height="96" fill="#8b8a7c"/>` + vl(78) + vl(42, W, '10 14') + carTop(60, 60, AMB, true)),
    what: 'Показывает край проезжей части.', todo: 'Её можно пересечь, чтобы остановиться на обочине или выехать с неё.',
    trap: 'Объезжать пробку по обочине — это запрещено.', memo: 'Линия сбоку — край дороги.' },
  { n: '1.3', name: 'Двойная сплошная', short: 'Двойная сплошная', pic: road(vl(47, W, '', 2.6) + vl(53, W, '', 2.6) + carTop(74, 62, AMB, true) + carTop(26, 34, '#9aa', false)),
    what: 'Разделяет встречные потоки на широких дорогах — где четыре полосы и больше.', todo: 'Пересекать нельзя: ни для обгона, ни для разворота, ни для поворота.',
    trap: 'Развернуться через двойную, «потому что никого нет». Это нарушение.', memo: 'Две линии — двойная стена.' },
  { n: '1.4', name: 'Жёлтая сплошная линия', short: 'Жёлтая сплошная', pic: road(curb(84) + vl(81, YEL, '', 4) + carTop(62, 50, AMB, true)),
    what: 'Показывает, где запрещена остановка. Её рисуют у края дороги или на бордюре.', todo: 'Не останавливайся вдоль этой линии, даже на минутку.',
    trap: 'Высадить пассажира «на секундочку» у жёлтой сплошной.', memo: 'Жёлтая сплошная — как знак «Остановка запрещена».' },
  { n: '1.5', name: 'Прерывистая линия', short: 'Прерывистая', pic: road(vl(50, W, '10 14') + carTop(70, 64, AMB, true) + carTop(30, 34, '#9aa', false)),
    what: 'Разделяет полосы или встречные потоки на двухполосной дороге.', todo: 'Пересекать можно: для перестроения, обгона или поворота.',
    trap: 'Перестраиваться без поворотника и не посмотрев в зеркала.', memo: 'Пунктир можно перешагнуть.' },
  { n: '1.6', name: 'Линия приближения', short: 'Линия приближения', pic: road(ln('M50 98 V36', W, 3, 'stroke-dasharray="18 6"') + ln('M50 30 V2', W, 3) + carTop(70, 72, AMB, true)),
    what: 'Длинные штрихи и короткие промежутки: скоро начнётся сплошная.', todo: 'Пересекать можно, но новый обгон не начинай — не успеешь.',
    trap: 'Начать обгон на линии приближения и упереться в сплошную.', memo: 'Штрихи стали длиннее — сплошная близко.' },
  { n: '1.7', name: 'Линия на перекрёстке', short: 'Пунктир на перекрёстке', pic: `<rect x="2" y="2" width="96" height="96" rx="6" fill="${ASPH}"/>` + ln('M38 98 V70 M62 98 V70 M38 30 V2 M62 30 V2', W, 3) + ln('M38 70 Q38 50 18 38 M62 70 V30', W, 2.4, 'stroke-dasharray="4 4"'),
    what: 'Короткие частые штрихи показывают полосы прямо на перекрёстке.', todo: 'Держись своей полосы, пока поворачиваешь.', trap: '', memo: 'Мелкий пунктир — подсказка, как пройти перекрёсток.' },
  { n: '1.8', name: 'Широкая прерывистая', short: 'Полоса разгона', pic: road(vl(36, W, '10 14') + ln('M68 98 V2', W, 6, 'stroke-dasharray="10 8"') + carTop(84, 66, AMB, true)),
    what: 'Отделяет полосу разгона или торможения от основной дороги.', todo: 'Съезжаешь — заранее уйди на полосу торможения. Въезжаешь — разгонись на полосе разгона и пропусти тех, кто едет по основной.',
    trap: 'Тормозить на основной дороге перед съездом.', memo: 'Толстый пунктир — полоса для разгона или торможения.' },
  { n: '1.9', name: 'Разметка реверсивных полос', short: 'Реверсивная', pic: road(vl(46, W, '10 14', 2.4) + vl(52, W, '10 14', 2.4) + `<rect x="20" y="8" width="60" height="14" rx="3" fill="${OFF}"/>` + T(35, 19, 11, '✕', RED) + T(65, 19, 12, '↓', '#4cd964')),
    what: 'Двойная прерывистая: границы полос, направление которых меняется в разное время.', todo: 'Смотри на реверсивные светофоры над полосами: красный крест — нельзя, зелёная стрелка — можно.',
    trap: '', memo: 'Двойной пунктир — полоса работает то туда, то обратно.' },
  { n: '1.10', name: 'Жёлтая прерывистая линия', short: 'Жёлтая прерывистая', pic: road(curb(84) + vl(81, YEL, '10 8', 4) + carTop(62, 50, AMB, true)),
    what: 'Показывает, где запрещена стоянка.', todo: 'Остановиться ненадолго можно, оставить машину и уйти — нельзя.',
    trap: '', memo: 'Жёлтый пунктир — как знак «Стоянка запрещена».' },
  { n: '1.11', name: 'Сплошная с прерывистой', short: 'Сплошная + прерывистая', pic: road(vl(47) + vl(53, W, '10 14') + carTop(72, 64, AMB, true) + carTop(28, 34, '#9aa', false)),
    what: 'Две линии рядом: одна сплошная, другая прерывистая.', todo: 'Со стороны прерывистой пересекать можно. Со стороны сплошной — только чтобы закончить обгон или объезд.',
    trap: 'Смотреть не на ту линию.', memo: 'Решает линия, которая ближе к тебе.' },
  { n: '1.12', name: 'Стоп-линия', short: 'Стоп-линия', pic: road(vl(50, W, '10 14') + `<rect x="52" y="40" width="44" height="6" fill="${W}"/>` + carTop(74, 64, AMB, true)),
    what: 'Поперечная линия перед перекрёстком или переходом.', todo: 'На красный или у знака STOP останавливайся перед ней, не заезжая на неё.',
    trap: 'Встать на стоп-линии или за ней — камеры за это штрафуют.', memo: 'Поперечная белая полоса — стоп здесь.' },
  { n: '1.13', name: 'Место, где нужно уступить дорогу', short: '«Зубы дракона»', pic: road(vl(50, W, '10 14') + [56, 66, 76, 86].map(x => `<path d="M${x - 4} 34 H${x + 4} L${x} 44 Z" fill="${W}"/>`).join('') + carTop(74, 68, AMB, true)),
    what: 'Треугольники поперёк полосы — остриём к тебе. Тут нужно уступить дорогу.', todo: 'Пропусти тех, кто едет по пересекаемой дороге. Если нужно — остановись перед линией.',
    trap: '', memo: 'Зубы смотрят на тебя — ты уступаешь.' },
  { n: '1.14.1', name: 'Пешеходный переход («зебра»)', short: 'Зебра', pic: road([10, 26, 42, 58, 74].map(x => `<rect x="${x}" y="38" width="10" height="24" fill="${W}"/>`).join('') + carTop(74, 82, AMB, true)),
    what: 'Пешеходный переход.', todo: 'Пропусти пешеходов, которые идут по переходу или уже ступили на него. Останавливаться на зебре нельзя.',
    trap: 'Проехать перед человеком, который «ещё далеко».', memo: 'Полоски зебры — дорожка для людей.' },
  { n: '1.16.1', name: 'Островок безопасности', short: 'Островок', pic: road(ln('M30 98 V70 L50 40 L70 70 V98', W, 3) + ln('M38 90 L50 76 M38 80 L50 66 M50 90 L62 76 M50 80 L62 66 M44 64 L56 64', W, 2)),
    what: 'Заштрихованная зона — островок, разделяющий потоки.', todo: 'Заезжать на неё нельзя.', trap: 'Срезать по штриховке, чтобы быстрее перестроиться.', memo: 'Штриховка — газон, нарисованный краской.' },
  { n: '1.17.1', name: 'Остановка автобусов', short: 'Жёлтая «пила»', pic: road(curb(84) + ln('M80 10 L72 20 L80 30 L72 40 L80 50 L72 60 L80 70 L72 80 L80 90', YEL, 3) + vl(70, YEL, '', 2)),
    what: 'Жёлтый зигзаг у края — место остановки автобусов (похожая разметка 1.17.2 — для такси).', todo: 'Не останавливайся на ней, если ты не автобус.',
    trap: 'Встать на остановке «на минутку», чтобы забрать друга.', memo: 'Жёлтая пила — место автобуса.' },
  { n: '1.18', name: 'Стрелки на полосах', short: 'Стрелки на асфальте', pic: road(vl(34, W, '10 14') + vl(66, W, '10 14') + ln('M18 86 V62 Q18 52 10 50', W, 4) + head(4, 49, 190, 7, W) + arrowUp(50, 50, W) + arrowUp(82, 50, W) + ln('M82 72 L90 64', W, 3) + head(94, 58, -45, 6, W)),
    what: 'Показывают, куда можно ехать из этой полосы.', todo: 'Займи полосу со своей стрелкой заранее. Из крайней левой полосы со стрелкой налево можно и развернуться, если это не запрещено.',
    trap: 'Повернуть не из той полосы.', memo: 'Стрелка на асфальте = стрелка на знаке.' },
  { n: '1.19', name: 'Стрелка перестроения', short: 'Стрелка перестроения', pic: road(vl(50, W, '10 14') + ln('M74 90 V66 Q74 50 60 42', W, 5) + head(52, 36, 215, 9, W)),
    what: 'Изогнутая стрелка: впереди сужение дороги или сплошная линия.', todo: 'Перестройся в ту сторону, куда показывает стрелка.', trap: '', memo: 'Стрелка гнётся — и ты перестраивайся.' },
  { n: '1.23.1', name: 'Полоса для автобусов', short: 'Буква «А»', pic: road(curb(88) + vl(62, W, '', 3) + T(76, 62, 26, 'А', W)),
    what: 'Буква «А» на полосе — полоса для автобусов и другого маршрутного транспорта.', todo: 'Не езди по ней. Заехать можно, только чтобы повернуть направо, если она отделена прерывистой.',
    trap: 'Объезжать по ней пробку — камеры это видят.', memo: 'Буква А — автобус.' },
  { n: '1.26', name: 'Вафельная разметка', short: 'Вафля', pic: road(`<rect x="18" y="18" width="64" height="64" fill="none" stroke="${YEL}" stroke-width="3"/>` + ln('M18 34 L66 82 M18 50 L50 82 M18 66 L34 82 M34 18 L82 66 M50 18 L82 50 M66 18 L82 34 M18 66 L66 18 M18 50 L50 18 M18 34 L34 18 M34 82 L82 34 M50 82 L82 50 M66 82 L82 66', YEL, 2)),
    what: 'Жёлтая клетка на перекрёстке.', todo: 'Не выезжай на неё, если впереди затор: останешься стоять на «вафле». Исключение — поворот, если мешают только встречные.',
    trap: 'Въехать «на хвосте» у впереди идущего и встать посреди перекрёстка.', memo: 'Клетка — место, где стоять нельзя.' },
];

// ---------- рисунки: светофоры ----------
const lamp = (cx, cy, c, on, blink) => `<circle cx="${cx}" cy="${cy}" r="9" fill="${on ? c : OFF}" ${on ? '' : 'stroke="#555" stroke-width="1"'}/>` +
  (on ? `<circle cx="${cx}" cy="${cy}" r="9" fill="${c}" opacity=".25" transform="translate(0 0)"/>` : '') +
  (blink ? `<circle cx="${cx}" cy="${cy}" r="13" fill="none" stroke="${c}" stroke-width="2" stroke-dasharray="3 3"/>` : '');
const light3 = (r, y, g, opts) => { opts = opts || {}; return `<rect x="36" y="12" width="28" height="76" rx="6" fill="${BLK}"/>` +
  lamp(50, 28, RED, r) + lamp(50, 50, '#f2b705', y, opts.by) + lamp(50, 72, GRN, g, opts.bg) + (opts.arrow ? `<rect x="64" y="62" width="22" height="22" rx="5" fill="${BLK}"/><circle cx="75" cy="73" r="8" fill="${opts.arrow === 'on' ? GRN : OFF}"/>` + ln('M70 73 H78', W, 2) + head(82, 73, 0, 5, W) : ''); };
const blinkTxt = t => T(50, 98, 9, t, '#65675e', 500);

const LIGHT = [
  { n: 'С1', name: 'Красный сигнал', short: 'Красный', pic: light3(1, 0, 0),
    what: 'Запрещает движение.', todo: 'Остановись перед стоп-линией. Поворачивать направо тоже нельзя, если нет отдельной зелёной стрелки.', trap: 'Повернуть направо на красный «как в кино» — у нас так нельзя.', memo: 'Красный — стоп для всех направлений.' },
  { n: 'С2', name: 'Красный и жёлтый вместе', short: 'Красный + жёлтый', pic: light3(1, 1, 0),
    what: 'Движение ещё запрещено, но скоро загорится зелёный.', todo: 'Приготовься тронуться, но жди зелёного.', trap: 'Трогаться, не дождавшись зелёного.', memo: 'Два огня сверху — «приготовься».' },
  { n: 'С3', name: 'Жёлтый сигнал', short: 'Жёлтый', pic: light3(0, 1, 0),
    what: 'Запрещает движение.', todo: 'Остановись. Ехать дальше можно, только если ты уже не успеваешь остановиться без резкого торможения.', trap: 'Разгоняться, чтобы «проскочить на жёлтый».', memo: 'Жёлтый — это не «быстрее», а «стоп, если можешь».' },
  { n: 'С4', name: 'Мигающий зелёный', short: 'Мигающий зелёный', pic: light3(0, 0, 1, { bg: 1 }) + blinkTxt('мигает'),
    what: 'Зелёный скоро закончится, следом загорится жёлтый.', todo: 'Не разгоняйся. Если далеко от перекрёстка — готовься остановиться.', trap: '', memo: 'Зелёный мигает — время кончается.' },
  { n: 'С5', name: 'Зелёная стрелка в дополнительной секции', short: 'Зелёная стрелка', pic: light3(1, 0, 0, { arrow: 'on' }),
    what: 'Можно ехать в сторону стрелки, даже если основной сигнал красный.', todo: 'Поворачивай, но пропусти тех, кто едет с других направлений, и пешеходов.', trap: 'Думать, что по стрелке ты главный.', memo: 'Стрелка разрешает, но не делает главным.' },
  { n: 'С6', name: 'Мигающий жёлтый', short: 'Мигающий жёлтый', pic: light3(0, 1, 0, { by: 1 }) + blinkTxt('мигает'),
    what: 'Светофор не регулирует перекрёсток — как будто его нет. Так же — когда светофор выключен.', todo: 'Смотри на знаки приоритета, а если их нет — пропускай тех, кто справа.',
    trap: 'Ехать как на зелёный.', memo: 'Мигает жёлтый — разбирайся по знакам.' },
  { n: 'С7', name: 'Светофор на железнодорожном переезде', short: 'Светофор переезда', pic: `<rect x="14" y="30" width="72" height="36" rx="18" fill="${BLK}"/>` + lamp(32, 48, RED, 1, 1) + lamp(68, 48, RED, 1, 1) + `<rect x="40" y="70" width="20" height="20" rx="10" fill="${BLK}"/>` + lamp(50, 80, '#e8eefc', 0),
    what: 'Два красных попеременно мигают — едет поезд, стой. Бело-лунный мигающий огонь — можно ехать через переезд.', todo: 'На мигающий красный остановись у стоп-линии или знака и жди.',
    trap: 'Объехать опускающийся шлагбаум.', memo: 'Красные мигают — поезд рядом.' },
  { n: 'С8', name: 'Реверсивный светофор', short: 'Реверсивный', pic: `<rect x="10" y="30" width="80" height="40" rx="6" fill="${BLK}"/>` + T(30, 60, 26, '✕', RED) + ln('M70 38 V56', '#4cd964', 5) + head(70, 64, 90, 10, '#4cd964'),
    what: 'Висит над полосой. Красный крест — по этой полосе ехать нельзя. Зелёная стрелка вниз — можно. Жёлтая косая стрелка — освободи полосу.', todo: 'Смотри на светофор над своей полосой.',
    trap: '', memo: 'Крест — нельзя, стрелка вниз — можно.' },
  { n: 'С9', name: 'Трамвайный светофор', short: 'Трамвайный', pic: `<rect x="34" y="10" width="32" height="80" rx="6" fill="${BLK}"/>` + [24, 44, 64].map((y, i) => `<circle cx="50" cy="${y + 6}" r="10" fill="${OFF}"/>` + (i === 2 ? ln(`M44 ${y} H56 M50 ${y} V${y + 12}`, W, 3) : '')).join(''),
    what: 'Белые огни в виде буквы «Т» — сигналы для трамвая.', todo: 'Водителю машины на них ориентироваться не нужно — смотри на свой светофор.', trap: '', memo: 'Буква Т — трамвай.' },
];

// ---------- рисунки: регулировщик ----------
// вид сверху: регулировщик в центре, грудь смотрит вниз; его правая рука — слева на рисунке
const ALLOW = {             // что можно машине, подъезжающей к ... (грудь, спина, левый бок, правый бок)
  out: { chest: 'none', back: 'none', left: 'sr', right: 'sr' },
  fwd: { chest: 'r', back: 'none', left: 'all', right: 'none' },
  up: { chest: 'none', back: 'none', left: 'none', right: 'none' },
};
const ALLOW_TXT = { none: 'Ехать нельзя', r: 'Только направо', sr: 'Прямо и направо', all: 'Во всех направлениях' };
const SIDE_TXT = { chest: 'к груди', back: 'к спине', left: 'к левому боку', right: 'к правому боку' };
const SIDE_POS = { chest: [50, 86, -90], back: [50, 14, 90], left: [86, 50, 180], right: [14, 50, 0] };
const cross = `<rect x="2" y="2" width="96" height="96" rx="6" fill="#d9d3c0"/><rect x="34" y="2" width="32" height="96" fill="${ASPH}"/><rect x="2" y="34" width="96" height="32" fill="${ASPH}"/>`;
function regTop(pose) {
  const arm = (x1, y1, x2, y2) => ln(`M${x1} ${y1} L${x2} ${y2}`, '#24364f', 4, 'stroke-linecap="round"');
  let a = '';
  if (pose === 'out') a = arm(41, 50, 30, 50) + arm(59, 50, 70, 50);
  if (pose === 'fwd') a = arm(41, 50, 40, 62) + ln('M40 62 L40 70', W, 3) + ln('M40 64 L40 66 M40 68 L40 70', RED, 3) + arm(59, 50, 60, 54);
  if (pose === 'up') a = `<circle cx="40" cy="50" r="4.5" fill="#24364f" stroke="${W}" stroke-width="1.5"/>` + arm(59, 50, 60, 54);
  return `<ellipse cx="50" cy="50" rx="10" ry="5.5" fill="#24364f"/>${a}<circle cx="50" cy="50" r="4.2" fill="${W}" stroke="#24364f" stroke-width="1.5"/><path d="M47 54 L50 57.5 L53 54 Z" fill="#24364f"/>`;
}
function regFront(pose, x, y, s) {           // маленький вид спереди (в углу)
  const g = (d, c, w) => ln(d, c || '#24364f', w || 3, 'stroke-linecap="round"');
  let a = pose === 'out' ? g('M8 15 H-8 M22 15 H38') : pose === 'fwd' ? g('M8 15 L12 22') + g('M12 22 L14 26', W, 2.5) + g('M22 15 L26 30') : g('M8 15 V-2') + g('M22 15 L26 30');
  return `<g transform="translate(${x} ${y}) scale(${s})"><rect x="-10" y="-6" width="50" height="46" rx="5" fill="${W}" opacity=".92"/><circle cx="15" cy="6" r="5" fill="#24364f"/><rect x="8" y="12" width="14" height="16" rx="3" fill="#24364f"/>${a}` +
    g('M11 28 V38 M19 28 V38') + `</g>`;
}
function badge(side, kind) {
  const [x, y] = SIDE_POS[side], c = kind === 'none' ? RED : GRN, t = { none: 'стоп', r: '→', sr: '↑ →', all: 'все' }[kind];
  const bx = x, by = side === 'chest' ? 90 : side === 'back' ? 10 : y;
  return `<rect x="${bx - 13}" y="${by - 8}" width="26" height="16" rx="8" fill="${c}"/>${T(bx, by + 4, 10, t, W)}`;
}
const sideLabels = T(50, 75, 7, 'грудь', W, 500) + T(50, 31, 7, 'спина', W, 500) + T(76, 40, 7, 'левый бок', W, 500) + T(24, 40, 7, 'правый бок', W, 500);
const regDiagram = pose => cross + sideLabels + Object.keys(SIDE_POS).map(s => badge(s, ALLOW[pose][s])).join('') + regTop(pose) + regFront(pose, 4, 4, .52);
const regQuizPic = (pose, side) => { const [x, y, deg] = SIDE_POS[side];
  return cross + sideLabels + `<g transform="rotate(${deg + 90} ${x} ${y})">${carTop(x, y, AMB, true)}</g>` + regTop(pose) + regFront(pose, 72, 72, .48); };

const REG = [
  { n: 'Р1', name: 'Руки в стороны или опущены', short: 'Руки в стороны', pic: regDiagram('out'), pose: 'out',
    what: 'Если ты подъезжаешь к левому или правому боку регулировщика — можно прямо и направо. Пешеходы могут переходить. Со стороны груди и спины — ехать нельзя.',
    todo: 'Смотри, каким боком регулировщик стоит к тебе.', trap: 'Повернуть налево, когда регулировщик стоит к тебе боком.', memo: 'Грудь и спина — стена. Сбоку — прямо и направо.' },
  { n: 'Р2', name: 'Правая рука вытянута вперёд', short: 'Рука вперёд', pic: regDiagram('fwd'), pose: 'fwd',
    what: 'Со стороны груди — только направо. Со стороны левого бока — во всех направлениях. Со стороны спины и правого бока — нельзя. Пешеходы переходят за спиной регулировщика.',
    todo: 'Найди, с какой стороны ты подъезжаешь, и вспомни стишок.', trap: 'Перепутать левый и правый бок регулировщика.',
    memo: 'Палка смотрит в рот — делай правый поворот. Палка смотрит вправо — ехать не имеешь права. Палка смотрит влево — поезжай как королева.' },
  { n: 'Р3', name: 'Рука поднята вверх', short: 'Рука вверх', pic: regDiagram('up'), pose: 'up',
    what: 'Движение всем запрещено во всех направлениях.', todo: 'Остановись. Если уже не успеваешь остановиться без резкого торможения — проезжай, как на жёлтый.', trap: '', memo: 'Рука вверх — стоп для всех, как жёлтый.' },
  { n: 'Р4', name: 'Регулировщик главнее всех', short: 'Кто главнее', pic: cross + regTop('fwd') + `<rect x="76" y="6" width="16" height="38" rx="3" fill="${BLK}"/><circle cx="84" cy="14" r="4.5" fill="${OFF}"/><circle cx="84" cy="25" r="4.5" fill="${OFF}"/><circle cx="84" cy="36" r="4.5" fill="${GRN}"/>`,
    what: 'Сигналы регулировщика главнее светофора, знаков и разметки.', todo: 'Если регулировщик показывает одно, а светофор другое — слушай регулировщика. Если он жезлом показывает на тебя — остановись там, где он укажет.',
    trap: 'Ехать на зелёный, когда регулировщик поднял руку.', memo: 'Человек главнее светофора.' },
];

// ---------- памятки ----------
const DTP = [
  ['Остановись и не трогай машину', 'Сразу остановись. Не передвигай машину и предметы, которые относятся к аварии, — пока не решишь, как оформлять.'],
  ['Аварийка и знак', 'Включи аварийку. Выставь знак аварийной остановки: в городе — не ближе 15 метров, за городом — не ближе 30 метров. За городом ночью выходи из машины в светоотражающем жилете.'],
  ['Есть пострадавшие? Звони 112', 'Если кто-то пострадал — звони 112 и окажи первую помощь, сколько можешь. Скорую вызывай сразу, не жди полицию.'],
  ['Сфотографируй всё', 'Сними общий план, положение машин, повреждения, номера, знаки и разметку рядом, следы на дороге. Фотографий много не бывает.'],
  ['Освободи дорогу, если никто не пострадал', 'Если людей не задело, а ваши машины мешают другим — после фото отъедьте к обочине.'],
  ['Европротокол или ГИБДД', 'Без пострадавших, две машины, у обоих ОСАГО и вы согласны, кто виноват, — можно оформить европротокол без ГИБДД, на бумаге или через Госуслуги. Если спорите или есть пострадавшие — вызывай ГИБДД.'],
  ['Не уезжай и не пей', 'Уехать с места ДТП — это лишение прав. До проверки на алкоголь пить нельзя совсем, даже «для успокоения».'],
  ['Позвони в страховую', 'Сообщи о ДТП своей страховой как можно скорее — сроки короткие. Спроси, какие документы нужны.'],
];
const WINTER = [
  ['Прогрей и очисти машину', 'В мороз дай двигателю поработать несколько минут, первые километры едь спокойно. Очисти от снега все стёкла, зеркала, фары и крышу — снег с крыши при торможении съедет на лобовое. Во дворе (жилой зоне) долго стоять с работающим мотором нельзя.'],
  ['Зимние шины обязательно', 'В декабре, январе и феврале ездить на летней резине запрещено. Лучше переобуться раньше — в Иркутске снег бывает уже в октябре.'],
  ['Дистанция в 2–3 раза больше', 'На снегу и льду машина тормозит намного дольше. Держись дальше от машины впереди.'],
  ['Тормози правильно', 'С ABS — нажми тормоз сильно и держи, машина сама не даст колёсам заблокироваться. Без ABS — тормози плавно, короткими нажатиями.'],
  ['Мосты замерзают первыми', 'На мостах через Ангару и Иркут лёд появляется раньше, чем на остальной дороге. Перед мостом сбавь скорость и не делай резких манёвров.'],
  ['Туман над Ангарой', 'Ниже ГЭС Ангара не замерзает и зимой парит — бывает густой туман. Включи ближний свет и противотуманки, сбавь скорость.'],
  ['Горки и подъёмы', 'Трогайся плавно, без пробуксовки. Не останавливайся посреди подъёма и держи дистанцию: машина впереди может покатиться назад.'],
  ['Если занесло', 'Не жми резко на тормоз. Убери ногу с газа и плавно поверни руль туда, куда заносит заднюю часть машины.'],
  ['Не грей машину в закрытом гараже', 'Выхлоп в закрытом помещении смертельно опасен — угарный газ не пахнет.'],
  ['Застрял за городом', 'Не уходи от машины, звони 112. Прогревайся периодически и следи, чтобы выхлопная труба не была засыпана снегом.'],
  ['Что возить зимой', 'Щётку, скребок, незамерзайку, буксировочный трос, провода для прикуривания, лопату, перчатки, плед и тёплые вещи.'],
];

// ---------- темы ----------
const TOPICS = {
  mark: { title: 'Дорожная <em>разметка</em>', intro: 'Линии и стрелки на асфальте. Зимой их видно хуже, поэтому полезно знать заранее, что где нарисовано.', items: MARK, prompt: 'Что это за разметка?' },
  light: { title: 'Светофоры и <em>регулировщик</em>', intro: 'Сначала сигналы светофора, потом жесты регулировщика. В тесте будут задачи: «вы подъезжаете к регулировщику — что можно?»', items: LIGHT.concat(REG), prompt: 'Что означает этот сигнал?' },
};
const GUIDES = {
  dtp: { title: 'Если случилось <em>ДТП</em>', intro: 'Спокойно, по шагам. Сохраните эту памятку — в стрессе голова работает плохо.', steps: DTP, calls: true },
  winter: { title: 'Зима в <em>Иркутске</em>', intro: 'В автошколе о зиме говорят мало, а у нас она полгода. Главное — заранее и плавно.', steps: WINTER },
};

// ---------- состояние ----------
const seen = new Set((() => { try { return JSON.parse(localStorage.getItem('nav_learn_seen') || '[]'); } catch (e) { return []; } })());
const saveSeen = () => { try { localStorage.setItem('nav_learn_seen', JSON.stringify([...seen])); } catch (e) {} };
let topic = 'mark', cur = 0, guide = 'dtp';
const show = id => window.show(id);
const stop = () => { if (window.stopSpeech) window.stopSpeech(); };
const say = t => { if (window.speak) window.speak(t); };

// ---------- каталог темы ----------
function openTopic(id) {
  stop(); topic = id; const t = TOPICS[id];
  el('lnTitle').innerHTML = t.title; el('lnIntro').textContent = t.intro;
  const done = t.items.filter(i => seen.has(id + i.n)).length;
  el('lnProg').textContent = `Изучено ${done} из ${t.items.length}`; el('lnBar').style.width = Math.round(done / t.items.length * 100) + '%';
  el('lnGrid').innerHTML = t.items.map((it, i) => `<button class="stile${seen.has(id + it.n) ? ' seen' : ''}" onclick="Learn.item(${i})">${svg(it.pic, 64)}<span class="sn">${it.n}</span><span class="st">${esc(it.short)}</span></button>`).join('');
  show('scrLearn'); el('scrLearn').scrollTop = 0;
}
function openItem(i) {
  stop(); const t = TOPICS[topic]; cur = (i + t.items.length) % t.items.length; const it = t.items[cur];
  seen.add(topic + it.n); saveSeen();
  el('liPic').innerHTML = svg(it.pic, 180);
  el('liNum').textContent = topic === 'mark' ? `Разметка ${it.n}` : it.n.startsWith('Р') ? 'Регулировщик' : 'Светофор';
  el('liName').textContent = it.name;
  [['liWhat', it.what], ['liTodo', it.todo], ['liTrap', it.trap], ['liMemo', it.memo]].forEach(([id, txt]) => { el(id).textContent = txt; el(id).parentElement.classList.toggle('hidden', !txt); });
  el('liPos').textContent = `${cur + 1} / ${t.items.length}`;
  show('scrLearnItem'); el('scrLearnItem').scrollTop = 0;
}
function listenItem() { const it = TOPICS[topic].items[cur]; say([it.name + '.', it.what, it.todo && 'Что делать: ' + it.todo, it.trap && 'Ошибка новичка: ' + it.trap, it.memo && 'Запомни: ' + it.memo].filter(Boolean).join(' ')); }

// ---------- памятки ----------
function openGuide(id) {
  stop(); guide = id; const g = GUIDES[id];
  el('gdTitle').innerHTML = g.title; el('gdIntro').textContent = g.intro;
  el('gdCalls').classList.toggle('hidden', !g.calls);
  el('gdSteps').innerHTML = g.steps.map(([h, t], i) => `<div class="card gdstep"><div class="gdnum">${i + 1}</div><div style="flex:1; min-width:0"><h3>${esc(h)}</h3><p>${esc(t)}</p></div>
    <button class="iconbtn" aria-label="Прослушать шаг ${i + 1}" onclick="Learn.sayStep(${i})"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M3 10v4M7 7v10M11 4v16M15 8v8M19 11v2"></path></svg></button></div>`).join('');
  show('scrGuide'); el('scrGuide').scrollTop = 0;
}
const sayStep = i => { const [h, t] = GUIDES[guide].steps[i]; say(`Шаг ${i + 1}. ${h}. ${t}`); };
const sayAll = () => say(GUIDES[guide].steps.map(([h, t], i) => `Шаг ${i + 1}. ${h}. ${t}`).join(' '));

// ---------- общий тест ----------
const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.random() * (i + 1) | 0; [a[i], a[j]] = [a[j], a[i]]; } return a; };
function nameQ(items, it, prompt) {             // «что это?» — 3 варианта из той же темы
  const opts = shuffle([it.name, ...shuffle(items.filter(x => x.name !== it.name)).slice(0, 2).map(x => x.name)]);
  return { pic: it.pic, q: prompt, opts, right: opts.indexOf(it.name), explain: it.memo || it.what, name: it.name };
}
function regQ() {
  const pose = shuffle(['out', 'fwd', 'fwd', 'up'])[0], side = shuffle(Object.keys(SIDE_POS))[0], ans = ALLOW[pose][side];
  const opts = ['none', 'r', 'sr', 'all'].map(k => ALLOW_TXT[k]);
  const it = REG.find(r => r.pose === pose);
  return { pic: regQuizPic(pose, side), q: `Регулировщик: «${it.name.toLowerCase()}». Вы (жёлтая машина) подъезжаете ${SIDE_TXT[side]}. Что можно?`, opts, right: opts.indexOf(ALLOW_TXT[ans]),
    explain: `${it.memo}`, name: ALLOW_TXT[ans] };
}
function signQ(top) {
  const L = (window.Signs ? Signs.list : []).filter(s => !top || s.top); if (!L.length) return null;
  const s = shuffle(L.slice())[0], pool = L.filter(x => x.name !== s.name);
  const same = shuffle(pool.filter(x => x.g === s.g)), other = shuffle(pool.filter(x => x.g !== s.g));
  const opts = shuffle([s.name, ...same.concat(other).slice(0, 2).map(x => x.name)]);
  return { pic: s.svg, q: 'Что означает этот знак?', opts, right: opts.indexOf(s.name), explain: s.memo || s.what, name: s.name };
}
function topicQs(id, n) {
  if (id === 'mark') return shuffle(MARK.slice()).slice(0, n).map(it => nameQ(MARK, it, 'Что это за разметка?'));
  const lights = shuffle(LIGHT.slice()).slice(0, Math.ceil(n / 2)).map(it => nameQ(LIGHT, it, 'Что означает этот сигнал?'));
  const regs = Array.from({ length: n - lights.length }, regQ);
  return shuffle(lights.concat(regs));
}

const Q = { list: [], i: 0, score: 0, right: 0, streak: 0, wrong: [], locked: false, kind: '', back: null };
function startQuiz(kind) {
  stop(); Q.kind = kind; Q.i = 0; Q.score = 0; Q.right = 0; Q.streak = 0; Q.wrong = [];
  if (kind === 'daily') {
    Q.list = [signQ(true), signQ(false), topicQs('mark', 1)[0], regQ(), nameQ(LIGHT, shuffle(LIGHT.slice())[0], 'Что означает этот сигнал?')].filter(Boolean);
    el('qzTitle').innerHTML = 'Тренировка <em>дня</em>';
  } else { Q.list = topicQs(kind, 8); el('qzTitle').innerHTML = kind === 'mark' ? 'Тест: <em>разметка</em>' : 'Тест: <em>светофоры</em>'; }
  el('qzEnd').classList.add('hidden'); el('qzBody').classList.remove('hidden');
  show('scrQuiz'); ask();
}
function ask() {
  Q.locked = false; const q = Q.list[Q.i];
  el('qzPos').textContent = `Вопрос ${Q.i + 1} из ${Q.list.length}`; el('qzScore').textContent = Q.score;
  el('qzDots').innerHTML = Q.list.map((_, k) => `<i class="${k < Q.i ? (Q.wrong.includes(k) ? 'bad' : 'ok') : k === Q.i ? 'cur' : ''}"></i>`).join('');
  el('qzPic').innerHTML = svg(q.pic, 170); el('qzQ').textContent = q.q;
  el('qzOpts').innerHTML = q.opts.map((o, i) => `<button class="qopt" data-i="${i}">${esc(o)}</button>`).join('');
  el('qzOpts').querySelectorAll('.qopt').forEach(b => b.onclick = () => answer(b));
  el('qzFeed').classList.add('hidden'); el('qzNext').classList.add('hidden');
}
function answer(btn) {
  if (Q.locked) return; Q.locked = true; const q = Q.list[Q.i], ok = +btn.dataset.i === q.right;
  el('qzOpts').querySelectorAll('.qopt').forEach(b => { b.disabled = true; if (+b.dataset.i === q.right) b.classList.add('right'); });
  if (ok) { Q.right++; Q.streak++; const p = 10 + (Q.streak >= 3 ? 5 : 0); Q.score += p;
    el('qzFeed').innerHTML = `<b class="ok-t">Верно! +${p}${Q.streak >= 3 ? ' · серия ×' + Q.streak : ''}</b><br>${esc(q.explain)}`; }
  else { btn.classList.add('wrong'); Q.streak = 0; Q.wrong.push(Q.i);
    el('qzFeed').innerHTML = `<b class="bad-t">Правильно: «${esc(q.opts[q.right])}».</b><br>${esc(q.explain)}`; }
  el('qzScore').textContent = Q.score; el('qzFeed').classList.remove('hidden'); el('qzNext').classList.remove('hidden');
  el('qzNext').textContent = Q.i + 1 < Q.list.length ? 'Дальше →' : 'Итоги';
}
async function next() {
  if (Q.i + 1 < Q.list.length) { Q.i++; ask(); return; }
  let bonus = 0, extra = '';
  if (Q.kind === 'daily') { const d = dailyDone(); if (d.fresh) { bonus = 20; extra = ` Серия: ${d.streak} ${window.plural ? plural(d.streak, 'день', 'дня', 'дней') : 'дн.'} подряд.`; } }
  Q.score += bonus;
  el('qzBody').classList.add('hidden'); el('qzEnd').classList.remove('hidden');
  el('qzRes').textContent = Q.score; el('qzSaved').textContent = '';
  el('qzResTxt').textContent = `${Q.right} из ${Q.list.length} верно.` + (bonus ? ` +${bonus} за тренировку дня.` : '') + extra;
  window.speak && window.speak(`Готово. ${Q.right} из ${Q.list.length} верно.${extra}`);
  if (Q.score > 0) try {
    const name = window.playerName ? window.playerName() : 'Игрок';
    await fetch('/api/score', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, score: Q.score, route: Q.kind === 'daily' ? 'Тренировка дня' : 'Тест: ' + (Q.kind === 'mark' ? 'разметка' : 'светофоры'),
        kind: Q.kind, right: Q.right, total: Q.list.length, wrong: Q.wrong.map(i => Q.list[i].name) }) });
    el('qzSaved').textContent = `+${Q.score} очков в рейтинг игрока «${name}».`;
  } catch (e) {}
  refreshDaily();
}
function quizBack() { stop(); if (Q.kind === 'daily') show('scrMenu'); else openTopic(Q.kind); }

// ---------- тренировка дня ----------
const today = (d) => (d || new Date()).toLocaleDateString('sv');
function dailyState() { try { return JSON.parse(localStorage.getItem('nav_daily') || '{}'); } catch (e) { return {}; } }
function dailyDone() {
  const st = dailyState(), t = today(); if (st.last === t) return { fresh: false, streak: st.streak || 1 };
  const y = new Date(); y.setDate(y.getDate() - 1);
  st.streak = st.last === today(y) ? (st.streak || 0) + 1 : 1; st.last = t;
  try { localStorage.setItem('nav_daily', JSON.stringify(st)); } catch (e) {}
  return { fresh: true, streak: st.streak };
}
function refreshDaily() {
  const st = dailyState(), t = today(), y = new Date(); y.setDate(y.getDate() - 1);
  const alive = st.last === t || st.last === today(y), streak = alive ? st.streak || 0 : 0, done = st.last === t;
  if (!el('dailyTxt')) return;
  el('dailyTxt').textContent = done ? `Сегодня выполнено ✓ · серия ${streak} ${plural(streak, 'день', 'дня', 'дней')}` :
    streak ? `Серия ${streak} ${plural(streak, 'день', 'дня', 'дней')} — не прерывайте!` : '5 вопросов в день: знаки, разметка, светофоры';
  el('dailyBtn').textContent = done ? 'Ещё раз' : 'Начать · +20';
}
const icon = {
  signs: () => window.Signs ? `<svg viewBox="0 0 100 100" width="40" height="40" aria-hidden="true">${Signs.list.find(s => s.n === '2.4').svg}</svg>` : '',
  mark: () => svg(MARK[10].pic, 40), light: () => svg(light3(0, 0, 1), 40), reg: () => svg(regTop('fwd').replace('<ellipse', '<circle cx="50" cy="50" r="40" fill="#e5e7e0"/><ellipse'), 40),
  dtp: () => svg(`<path d="M50 8 L94 86 H6 Z" fill="${W}" stroke="${RED}" stroke-width="10" stroke-linejoin="round"/>`, 40),
  winter: () => svg(`<g stroke="#2f80fa" stroke-width="7" stroke-linecap="round"><path d="M50 10 V90 M15 30 L85 70 M15 70 L85 30"/><path d="M40 16 L50 26 L60 16 M40 84 L50 74 L60 84"/></g>`, 40),
};
function menuIcons() { Object.keys(icon).forEach(k => { const e = el('ic_' + k); if (e && !e.innerHTML) e.innerHTML = icon[k](); }); refreshDaily(); }

window.Learn = { back() { openTopic(topic); }, topic: openTopic, item: openItem, prev() { openItem(cur - 1); }, next() { openItem(cur + 1); }, listen: listenItem, stop,
  guide: openGuide, sayStep, sayAll, quiz: startQuiz, quizNext: next, quizBack, topicQuiz() { startQuiz(topic); }, menuIcons, refreshDaily,
  _test: { MARK, LIGHT, REG, ALLOW } };
})();
