# Пошук простих чисел у великому діапазоні — PARCS / Google Cloud

Навчальний проєкт на основі [Hummer12007/parcs-python](https://github.com/Hummer12007/parcs-python).
Збережено master, реєстрацію worker, планувальник, передавання Solver та Pyro4 RPC оригінального PARCS.
Це адаптація платформи, а не реалізація через multiprocessing.

**Стан:** алгоритм та інтеграцію перевірено локально. Результати Google Cloud з'являться після запуску наведених команд у вашому проєкті. Готових хмарних вимірювань у пакеті немає.

## Алгоритм

Для включного діапазону [L, R] master обчислює прості числа до floor(sqrt(R)).
Діапазон ділиться на N суміжних частин без перекриття. Кожен worker виконує
сегментоване решето: для кожного базового простого p викреслює кратні від
max(p², ceil(start/p)*p). Числа, що залишилися, — прості.
Обробка блоками по 1 000 000 чисел обмежує пам'ять. Числа 0 та 1 виключаються.
Master одночасно надсилає всі асинхронні RPC-запити, після чого очікує результати.

Режим N=0 — те саме решето послідовно на master. N=1..4 — обчислення на
відповідній кількості окремих worker VM. Усі 4 worker залишаються зареєстрованими;
обчислювальні виклики отримують лише перші N, впорядковані за внутрішньою IP-адресою.
На кожній VM один Solver-потік обчислює одну частину; два vCPU VM не означають два воркери.

Для великого діапазону повертаються кількість, сума, перше та останнє просте число.
Кожне просте число знаходиться, але великий список не передається мережею.
Для демонстрації `collect=true` повертає повний список (діапазон до мільйона чисел).
Це точний алгоритм, без імовірнісних тестів простоти.

## 1. Підготовка Cloud Shell

Розпакуйте ZIP у домашню директорію Cloud Shell. Потрібен активний trial і права
створення VM, VPC/firewall та доступу IAP SSH. Для власника персонального проєкту
зазвичай достатньо наявних прав; організаційні політики можуть накладати обмежження.

```bash
cd ~/parcs-primes-lab
gcloud config set project engaged-symbol-512807-b9
gcloud config set compute/region europe-north1
gcloud config set compute/zone europe-north1-a
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m unittest discover -s tests
```

Колеги мають замінити project ID на власний. Не змінюйте регіон без відповідної зміни зони.

## 2. Створення п'яти VM

```bash
bash cloud/deploy.sh
```

Скрипт створює `master`, `worker-1`, `worker-2`, `worker-3`, `worker-4`:
Debian 12, e2-standard-2 (2 vCPU, 8 GiB), 10 GB стандартного диска на VM,
окрема VPC `parcs-lab`, приватні IP 10.42.0.10–14. На кожній VM будується Docker-образ
Python 3.12 з цього коду. Вихідні з'єднання використовують тимчасові зовнішні IP.
HTTP 8080 і Pyro 9090 доступні лише між VM з тегом parcs-lab; SSH — через IAP.
Не створюйте правило allow-all. PARCS виконує завантажений Python-код, тому його
навчальний вебінтерфейс не повинен бути відкритий у публічний Інтернет.

Створення VM використовує кошти trial, а не безлімітний Free Tier. Після роботи
збережіть результати й зупиніть або видаліть VM. Скрипт не змінює тариф billing.
Якщо з'явилась помилка, збережіть її повний текст. Частина VM могла вже створитися;
не запускайте створення повторно навмання. Скрипт навмисно відмовляється перезаписувати наявні VM.

## 3. Доступ до PARCS

У першій вкладці Cloud Shell:

```bash
cd ~/parcs-primes-lab
bash cloud/tunnel.sh
```

Команда залишається працювати — це нормально. Відкрийте другу вкладку термінала
кнопкою `+`. У Cloud Shell виберіть **Web Preview → Preview on port 8080**.
На сторінці `/workers` повинні бути чотири worker. Зробіть скриншот.
Також зробіть скриншот списку VM у Compute Engine (master + 4 worker).
SSH port forwarding підтримується офіційним `gcloud compute ssh`:
https://docs.cloud.google.com/sdk/gcloud/reference/compute/ssh

У другій вкладці:

```bash
cd ~/parcs-primes-lab
source .venv/bin/activate
curl -fsS http://127.0.0.1:8080/api/worker | python -m json.tool
```

## 4. Вимірювання

```bash
python lab/benchmark.py --lo 2 --hi 100000000 --repeats 3 --out results/cloud
```

Спочатку перевіряються всі прості до 100 в усіх п'яти режимах. Потім виконуються
3 повтори кожного режиму, порядок змішується з фіксованим seed=42. Вибір медіани
зменшує вплив окремих викидів. Усі режими мають повернути однакові результати.
Кожен паралельний запуск також перевіряє різні hostname воркерів.

`seconds` вимірюється на master через `perf_counter`: від генерації базових простих
до отримання та об'єднання результатів. Час включає RPC-передавання даних,
але не створення VM, Docker build, завантаження Solver, очікування в черзі та запис JSON.
Це час алгоритму, а не час розгортання. Послідовний режим виконується на VM такого
самого типу, як worker. Не запускайте кілька benchmark одночасно.

Файли:

- `results/nodes.txt` — список машин після розгортання;
- `results/cloud/workers.json` — зареєстровані worker;
- `demo-0.json` … `demo-4.json` — точні списки простих до 100;
- `raw.json` — усі вимірювання, hostname та межі частин;
- `summary.csv`, `table.md` — таблиця медіан, мінімумів/максимумів і прискорення;
- `timing.svg` — графік; відкривається браузером і вставляється у звіт.

Для повторного експерименту вкажіть іншу директорію, наприклад `--out results/cloud-2`.
Якщо час надто короткий, збільшіть `--hi` для ВСІХ режимів, а не лише одного.
Прискорення S(N)=Tseq/TN, ефективність E(N)=S(N)/N. Прискорення не обов'язково
лінійне: впливають RPC, генерація базових простих та продуктивність VM.

## 5. Збереження результатів і GitHub

```bash
zip -r ~/parcs-results.zip results
cloudshell download ~/parcs-results.zip
```

Створіть на GitHub порожній репозиторій `parcs-primes-lab`. У Cloud Shell:

```bash
git init
git add .
git commit -m "PARCS prime search lab with cloud benchmarks"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/parcs-primes-lab.git
git push -u origin main
```

Замініть YOUR_USERNAME. Якщо Git попросить ім'я/email, задайте свої `git config`.
Для push потрібна авторизація GitHub (наприклад `gh auth login`, якщо gh доступний).
Не вставляйте токени у код чи README. Заповніть `REPORT.md` фактичними результатами,
скриншотами та посиланням на свій репозиторій.

## 6. Завершення роботи

Після завантаження результатів зупиніть VM:

```bash
bash cloud/stop.sh
```

Диски зупинених VM залишаються. Коли демонстрація завершена й дані збережено,
видаліть створені цим проєктом VM, їх boot-диски та окрему мережу:

```bash
bash cloud/delete.sh
```

gcloud запитає підтвердження видалення. Не видаляйте ресурси до збереження результатів.
Для відновлення після зупинки використайте `gcloud compute instances start master worker-1 worker-2 worker-3 worker-4 --zone=europe-north1-a`,
після запуску знову відкрийте тунель. Docker перезапускає PARCS автоматично.

## Перевірки та виправлення

```bash
python -m unittest discover -s tests
python -m tests.integration
```

Інтеграційний тест запускає master і 4 worker окремими локальними процесами,
реально завантажує Solver через PARCS і перевіряє режими N=0..4.
Цей тест НЕ є хмарним вимірюванням продуктивності.
Docker build і gcloud deployment необхідно перевірити у Cloud Shell.

Перелік змін платформи — `COMPATIBILITY.md`. Оригінальний README збережено як
`UPSTREAM_README.md` для атрибуції; його старі команди не використовуються.
Методичні матеріали:
https://mi.csc.knu.ua/wp-content/uploads/2025/09/PARCS-Python_Google_Cloud_0925.pdf

Старий create-with-container замінено звичайними VM з Docker, бо Google
депрекував контейнерний агент:
https://docs.cloud.google.com/compute/docs/containers/deploying-containers
