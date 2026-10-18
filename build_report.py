"""Build the Ukrainian report from actual, persisted experiment evidence."""
from pathlib import Path
import json
import statistics
import textwrap
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle, Preformatted
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4

ROOT = Path(__file__).resolve().parent
E = ROOT/'evidence'
OUT = ROOT/'output/pdf/Лабораторна_1_Weather_Mock_Терніков_П423.pdf'
pdfmetrics.registerFont(TTFont('Arial', 'C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold', 'C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFont(TTFont('Mono', 'C:/Windows/Fonts/DejaVuSansMono.ttf'))
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyUA', fontName='Arial', fontSize=10.5, leading=15, spaceAfter=9))
styles.add(ParagraphStyle(name='HeadingUA', fontName='ArialBold', fontSize=17, leading=22, textColor=colors.HexColor('#153657'), spaceAfter=16))
styles.add(ParagraphStyle(name='SmallUA', fontName='Arial', fontSize=9, leading=12, spaceAfter=8))
styles.add(ParagraphStyle(name='TitleUA', fontName='ArialBold', fontSize=23, leading=31, alignment=TA_CENTER, textColor=colors.HexColor('#153657'), spaceAfter=22))
styles.add(ParagraphStyle(name='CenterUA', parent=styles['BodyUA'], alignment=TA_CENTER))
styles.add(ParagraphStyle(name='CodeUA', fontName='Mono', fontSize=7.1, leading=10, spaceAfter=8))
story = []


def p(text, style='BodyUA'):
    story.append(Paragraph(escape(text).replace('\n', '<br/>'), styles[style]))


def title(text):
    p(text, 'HeadingUA')


def page():
    story.append(PageBreak())


def code(text):
    wrapped = []
    for line in text.splitlines():
        wrapped.extend(textwrap.wrap(line, width=100, replace_whitespace=False,
                                     drop_whitespace=False) or [''])
    story.append(Preformatted('\n'.join(wrapped), styles['CodeUA']))


def photo(name, caption, height=520):
    from PIL import Image as PILImage
    with PILImage.open(E/name) as im:
        w, h = im.size
    scale = min(499/w, height/h)
    story.append(Image(str(E/name), width=w*scale, height=h*scale))
    story.append(Spacer(1, 10))
    p(caption, 'SmallUA')


def table(rows, widths):
    t = Table([[Paragraph(escape(str(c)), styles['SmallUA']) for c in row] for row in rows], colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), colors.HexColor('#dce9f4')),
                          ('GRID', (0,0), (-1,-1), .4, colors.HexColor('#b6c5d5')),
                          ('VALIGN', (0,0), (-1,-1), 'TOP'),
                          ('LEFTPADDING', (0,0), (-1,-1), 8), ('RIGHTPADDING', (0,0), (-1,-1), 8),
                          ('TOPPADDING', (0,0), (-1,-1), 7)]))
    story.append(t)
    story.append(Spacer(1, 12))


r = json.loads((E/'udp_10.json').read_text())
b = json.loads((E/'udp_0.json').read_text())
timeouts = [x['elapsed_ms'] for x in r['packets'] if not x['received']]
mean = statistics.mean(x['elapsed_ms'] for x in r['packets'] if x['received'])

story.append(Spacer(1, 65))
p('ОРГАНІЗАЦІЯ КОМП’ЮТЕРНИХ МЕРЕЖ', 'CenterUA')
story.append(Spacer(1, 40))
p('Лабораторна робота №1', 'TitleUA')
p('Розробка мережевого клієнт-серверного додатку з використанням сокетного інтерфейсу (Socket API) для протоколів TCP та UDP', 'CenterUA')
story.append(Spacer(1, 25))
p('Варіант 16 - Weather Mock', 'TitleUA')
story.append(Spacer(1, 50))
p('Виконав: Терніков Дмитро Романович\nГрупа: П-423', 'CenterUA')
story.append(Spacer(1, 75))
p('18 жовтня 2026 року', 'CenterUA')
page()

title('1. Мета, середовище та архітектура')
p('Мета: освоїти BSD Socket API, створити власний прикладний протокол поверх TCP і UDP, реалізувати паралельне обслуговування клієнтів та дослідити таймаути і втрати датаграм.')
p('Роботу виконано на комп’ютері користувача, Windows 10 x64, Python 3 зі стандартною бібліотекою. Захоплення: Wireshark 4.6.9, Npcap 1.88, dumpcap на адаптері NPF_Loopback. Адреса досліду 127.0.0.1; TCP-порт 9000, UDP-порт 9001. Зовнішній сервіс погоди не використовується.')
p('TCPServer використовує ThreadingMixIn: кожний прийнятий клієнт обслуговується окремим потоком. UDP-приймач працює паралельно з TCP, а окремий потік кожні 2 секунди розсилає штормові попередження підписникам. Журнал містить час, IP, ефемерний порт, команди, завершення сеансів та відкинуті запити.')
table([['Компонент', 'Призначення'], ['weather_mock.py server', 'TCP + UDP, логування, mock-погода, Emergency Alert'], ['weather_mock.py tcp', 'Інтерактивні GET_WEATHER City та EXIT'], ['weather_mock.py udp', '100 Packet #N, ACK, таймаут 1 с, підрахунок втрат'], ['weather_mock.py alerts', 'Підписка й прийом попереджень'], ['test_weather.py', '5 інтеграційних тестів через справжні сокети'], ['run_experiment.py', 'Повторення досліду та перегляд збережених результатів']], [160,339])
p('Погода генерується детерміновано через SHA-256 назви міста: температура від -20 до 40 °C, вологість 20-100%, вітер 0-30 м/с. Прапорець mock=true однозначно вказує на навчальні дані.')
p('Обмеження: це навчальний сервер без автентифікації, шифрування та обмеження кількості потоків. Для досліду він слухає лише loopback. Результати локальної мережі не є оцінкою поведінки інтернет-з’єднання.')
page()

title('2. Прикладний протокол і запуск')
p('TCP: кодування UTF-8; запит завершується LF, відповідь - JSON + LF. Одне з’єднання підтримує кілька команд. Межі TCP-сегментів не визначають межі команд: readline збирає рядок із потоку. Максимальний запит - 4096 байтів разом із LF; надмірний або незавершений кадр спричиняє помилку та закриття.')
code('GET_WEATHER Kyiv\n{"status":"OK","city":"Kyiv","temperature_c":2,\n "humidity_pct":58,"wind_m_s":15.4,"mock":true}\nEXIT\n{"status":"BYE"}')
p('Невідома команда: UNKNOWN_COMMAND; некоректне місто: INVALID_CITY; невірне кодування: INVALID_UTF8. Міста з пробілами та кирилицею підтримуються. Після BYE сервер закриває сеанс; клієнт закриває файловий об’єкт і сокет.')
p('UDP: Packet #N отримує JSON {type: ACK, seq: N}. За drop_every=10 сервер не відповідає на номери, кратні 10. Відкидання детерміноване за номером, тому дослід відтворюваний. Клієнт послідовно надсилає 100 запитів; перевіряє джерело та номер ACK, ігнорує сторонні або застарілі відповіді до абсолютного дедлайну 1 с.')
p('SUBSCRIBE реєструє адресу UDP-слухача та повертає SUBSCRIBED. Сервер надсилає EMERGENCY_ALERT з номером і текстом MOCK: storm warning кожному слухачу окремою UDP-датаграмою. Це unicast-розсилання за списком підписок. UNSUBSCRIBE скасовує підписку; без поновлення вона спливає за 300 с.')
p('У різних терміналах із папки проєкту (Python 3):')
code('python weather_mock.py server\npython weather_mock.py tcp\npython weather_mock.py alerts\npython weather_mock.py udp --output result.json\npython -m unittest -v test_weather')
p('На цьому комп’ютері launch.ps1 знаходить наявний Python із середовища Codex; наприклад ./launch.ps1 server або ./launch.ps1 tcp. Контрольний запуск: server --drop-every 0. Зупинка сервера: Ctrl+C. Точні команди та структура доказів наведені також у README.md.')
page()

title('3. Реальні результати TCP')
p('Одночасно відкрито 4 TCP-сеанси. Бар’єр у досліді змушує всі чотири з’єднання бути відкритими до надсилання запитів та завершення перевірки. Ефемерні порти: 64341, 64343, 64344, 64342. У журналі видно окремі потоки та перекриття часу сеансів.')
photo('tcp_screenshot.png', 'Рис. 1. Скриншот панелі з фактичними записами чотирьох паралельних TCP-сеансів. Панель відображає збережені результати, а не чотири відкриті термінали.', height=375)
p('Для Kyiv отримано 2 °C, 58%, 15,4 м/с; для Lviv 29 °C, 36%, 21,2 м/с; для Odesa 27 °C, 40%, 10,1 м/с; для Dnipro -8 °C, 89%, 18,6 м/с. Невідома команда повернула помилку. Після EXIT кожний клієнт отримав BYE та EOF.')
p('Окремо запущено саме консольний TCP-клієнт зі stdin: GET_WEATHER Київ, EXIT. Його справжній вивід збережено у evidence/tcp_client.txt. Тести також перевірили фрагментацію запиту і кілька команд в одному надсиланні.')
page()

title('4. UDP: таймаути, втрати та попередження')
table([['Режим', 'Надіслано', 'Отримано', 'Втрачено', 'Частка'], ['drop_every=10', r['sent'], r['received'], r['lost'], f"{r['loss_pct']}%"], ['drop_every=0', b['sent'], b['received'], b['lost'], f"{b['loss_pct']}%"]], [155,86,86,86,86])
p('Packet Loss Ratio = (100 - 90) / 100 × 100%% = 10%%. Таймаути: #10, #20, #30, #40, #50, #60, #70, #80, #90, #100. Виміряний час очікування: від %.0f до %.0f мс; перевищення 1000 мс пояснюється плануванням ОС. Середній прикладний RTT успішних відповідей: %.3f мс.' % (min(timeouts), max(timeouts), mean))
photo('udp_screenshot.png', 'Рис. 2. Знімок вікна зі справжніми таймаутами, контрольним запуском, двома слухачами Emergency Alert і підсумком тестів.', height=345)
p('Два підписники (порти 57760 та 57761) отримали штормове попередження seq=2. Дані збережено у alerts.txt та кадрах 96, 98. UDP не має прапорів SYN/ACK/FIN; його заголовок містить порти, довжину й контрольну суму.')
p('Вимірюється відсутність прикладної відповіді, а не фізична втрата датаграми в мережі: відкинутий сервером запит залишається видимим у дампі. Контрольний дослід підтвердив 0% втрат при вимкненому моделюванні.')
page()

title('5. Аналіз трафіку Wireshark')
p('Захоплення виконано dumpcap із пакета Wireshark, фільтр tcp port 9000 or udp port 9001; файл traffic.pcapng містить 489 кадрів. Відкрито у Wireshark. Для першого потоку застосовано tcp.stream == 0.')
photo('wireshark_tcp.png', 'Рис. 3. Справжнє вікно Wireshark: SYN (кадр 1), SYN+ACK (8), ACK (11), прикладні дані та FIN+ACK під час закриття.', height=410)
table([['Кадр', 'Напрямок', 'Прапори', 'Значення'], ['1', '64341 → 9000', '0x0002 SYN', 'Початок з’єднання'], ['8', '9000 → 64341', '0x0012 SYN, ACK', 'Відповідь сервера'], ['11', '64341 → 9000', '0x0010 ACK', 'Завершення handshake'], ['67 / 71', 'Сервер / клієнт', '0x0011 FIN, ACK', 'Коректне завершення']], [48,125,130,196])
page()
title('5.1. Датаграма штормового попередження')
photo('wireshark_udp.png', 'Рис. 4. Справжня UDP-датаграма Emergency Alert, фільтр frame.number == 96.', height=420)
p('Кадр 96: 127.0.0.1:9001 → 127.0.0.1:57760, UDP Length=94 байти: 8 байтів заголовка та 86 байтів JSON із LF. У кадрі 98 те саме попередження надіслано другому підписнику. З’єднання та тристороннього рукостискання UDP не встановлює.')
code('{"type": "EMERGENCY_ALERT", "seq": 2,\n "message": "MOCK: storm warning", "mock": true}')
p('Докази: traffic.pcapng - первинне захоплення; packet_fields.csv - експорт полів; tcp_packets.txt - список першого потоку; udp_packet.txt - повний розбір кадру 96. Packet #10 присутній у мережевому захопленні, але сервер не надсилає відповідний ACK. Наступний запит починається після таймауту.')
page()

title('6. Тестування та висновки')
code((E/'tests.txt').read_text(encoding='utf-8'))
p('Перевірено: одночасні сеанси й EXIT/EOF; правильне складання фрагментованого TCP-запиту та розбір кількох рядків; кирилицю й помилки протоколу; обмеження розміру кадру; UDP-таймаут і відновлення на наступному номері; розсилання двом підписникам. Усі 5 інтеграційних тестів пройшли на реальних loopback-сокетах.')
p('Результат: створено багатопотоковий TCP-сервер Weather Mock, консольний TCP-клієнт, UDP-приймач, клієнт дослідження втрат та модуль штормових попереджень. Фреймінг через LF коректно відокремлює повідомлення в TCP-потоці. Локальні TCP-сеанси завершуються BYE і FIN/ACK; UDP-клієнт самостійно виявляє відсутність відповіді за таймаутом.')
p('За відкидання кожного десятого UDP-запиту зафіксовано 10% втрат відповідей, а без відкидання - 0%. Збережено справжній дамп трафіку, журнали й скриншоти. Це підтверджує реалізацію вимог у локальному середовищі; багатокомп’ютерну мережу, мережеві збої та навантаження великої кількості клієнтів окремо не досліджували.')
p('Git-репозиторій створено локально. Публікацію на зовнішній сервіс не виконано, оскільки адресу віддаленого репозиторію не надано. Історичний крок публікації початкового коду перед розробкою не відтворювався заднім числом.')
page()

title('7. Відповіді на контрольні запитання')
p('1. Чим accept() відрізняється від listen()? Що повертає accept()?', 'SmallUA')
p('listen(backlog) переводить прив’язаний TCP-сокет у режим очікування вхідних з’єднань і налаштовує чергу. accept() забирає встановлене з’єднання із черги та повертає новий сокет для конкретного клієнта й адресу цього клієнта. Слухаючий сокет залишається доступним для наступних підключень.')
p('2. Чому UDP не потребує listen() та accept()?', 'SmallUA')
p('UDP не встановлює транспортного з’єднання. Після socket(SOCK_DGRAM) і bind() сервер отримує окремі датаграми через recvfrom(), який повертає також адресу відправника. Відповідь надсилається sendto(). Новий сокет для кожного клієнта не потрібний.')
p('3. Socket Exhaustion і TIME_WAIT.', 'SmallUA')
p('Socket Exhaustion - вичерпання ресурсів сокетів: дескрипторів, пам’яті або доступних ефемерних портів. Активна сторона закриття TCP зазвичай перебуває у TIME_WAIT протягом 2MSL, щоб старі сегменти не потрапили в новий сеанс і можна було повторно підтвердити FIN. Велика кількість коротких з’єднань може вичерпати доступні локальні порти для заданих кінцевих точок. Допомагають повторне використання встановлених з’єднань і своєчасне закриття ресурсів; SO_REUSEADDR не є універсальним усуненням TIME_WAIT.')
p('4. Що станеться при раптовій зупинці процесу сервера?', 'SmallUA')
p('Результат залежить від стану сокета та ОС. При скиданні з’єднання ядро надсилає RST, а клієнт може отримати ConnectionResetError. Проте саме завершення процесу, навіть kill -9, не гарантує RST: ядро закриває дескриптори і може виконати звичайне закриття з FIN, тоді recv() поверне b\'\'. Непрочитані дані або абортивне закриття можуть спричинити RST. Якщо зник весь вузол чи зв’язок, негайного прапора може не бути, і збій виявиться через повторні передачі та таймаути. У цьому досліді зафіксовано штатне EXIT/FIN; аварійне завершення окремо не вимірювали.')
page()
title('7. Відповіді (продовження)')
p('5. Неблокуючий recv() і таймаут.', 'SmallUA')
p('У Python sock.setblocking(False) робить операції неблокуючими: за відсутності даних recv() піднімає BlockingIOError. Готовність зручно очікувати через selectors або select. sock.settimeout(1.0) задає обмежене очікування: за відсутності даних буде socket.timeout. У UDP-клієнті використано дедлайн time.monotonic(), щоб сторонні або запізнілі відповіді не подовжували загальний час очікування потрібного ACK.')
p('6. Заголовки в TCP-потоці та framing problem.', 'SmallUA')
p('TCP передає впорядкований потік байтів, а не повідомлення. Один sendall() може читатися кількома recv(), а кілька надсилань можуть об’єднатися в одному читанні. Прикладний заголовок, наприклад поле довжини, теж є частиною цього потоку, тому його потрібно накопичити й розібрати, а потім дочитати визначену кількість байтів. Фреймінг - правило встановлення меж повідомлень: фіксована довжина, префікс довжини або роздільник. У цій роботі використано LF і обмежений readline(); це не залежить від меж TCP-пакетів. UDP зберігає межі датаграм, але не гарантує доставку та порядок.')
title('8. Матеріали та відтворення')
p('Джерело завдання: наданий PDF «Лабораторна робота №1 (1)-1.pdf», копія assignment.pdf у проєкті. Первинні результати отримано запуском run_experiment.py на комп’ютері користувача 18.10.2026. Окремі тести запускаються python -m unittest -v test_weather.')
p('У додатках наведено повний код сервера/клієнтів і тестів. Файл run_experiment.py та сценарій побудови звіту доступні у комплекті проєкту. Результати у звіті взяті зі збережених файлів evidence; значення не підставлялися як очікувані результати.')
p('Для перегляду захоплення відкрийте evidence/traffic.pcapng у Wireshark. Для запуску серверів і клієнтів скористайтеся README.md та launch.ps1. На інших комп’ютерах достатньо встановленого Python 3 для основної програми.')

for filename, label in [('weather_mock.py', 'Додаток А. Повний код сервера та клієнтів'), ('test_weather.py', 'Додаток Б. Інтеграційні тести')]:
    page()
    title(label)
    p(filename, 'SmallUA')
    code((ROOT/filename).read_text(encoding='utf-8'))


def footer(c, doc):
    c.setStrokeColor(colors.HexColor('#b6c5d5'))
    c.line(48, 37, A4[0]-48, 37)
    c.setFont('Arial', 8)
    c.setFillColor(colors.HexColor('#526477'))
    c.drawString(48, 23, 'Weather Mock | Варіант 16 | Терніков Д. Р., П-423')
    c.drawRightString(A4[0]-48, 23, str(doc.page))


OUT.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=48, rightMargin=48,
                  topMargin=45, bottomMargin=52, title='Лабораторна №1 - Weather Mock',
                  author='Терніков Дмитро Романович').build(story, onFirstPage=footer, onLaterPages=footer)
print(OUT)
