See description [in English here](./README.md).
<br>
<br>

# Home Assistant GSM Call

[![Добавить репозиторий в HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=black-roland&repository=homeassistant-gsm-call&category=integration)

Пользовательский компонент для совершения телефонных звонков из Home Assistant с использованием 3G/4G, LTE модемов.

Основная задумка в том, чтобы задействовать модем для экстренного оповещения о важных событиях в умном доме. Но оповещениями всё не ограничивается и интеграция может быть полезна и в других сценариях, например для открытия ворот.

## Установка

Интеграцию можно установить с помощью HACS. Для этого нажмите голубую кнопку выше или добавьте репозиторий вручную:

1. Перейдите в _HACS_ → _Интеграции_.
2. В правом верхнем углу выберите трёхточечное меню, а затем выберите _Пользовательские репозитории_.
3. Вставьте `black-roland/homeassistant-gsm-call`.
4. Выберите _Интеграция_ в поле _Категория_.
5. Нажмите _Сохранить_.
6. Установите «GSM Call».

## Настройка и использование

Компонент настраивается через `configuration.yaml`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0 # путь до модема
```

Путь до модема можно получить, [нажав на «Всё оборудование»](https://my.home-assistant.io/redirect/hardware/).

После редактирования конфига потребуется перезапустить Home Assistant. Чтобы позвонить, используйте службу `notify.call`. Номер телефона для дозвона указывается в `target`:

```yaml
action:
  service: notify.call
  data:
    target: "+71234567890"
    message: "Обязательное поле в HASS, но компонент его не использует — можете указать любой текст"
```

### Продолжительность звонка

По умолчанию вызываемый телефон будет звонить в течение 30 секунд. Это время можно изменить с помощью параметра `call_duration_sec`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0
    call_duration_sec: 40
```

Примечания:
- Отсчёт времени начинается с момента, когда вызываемый телефон начинает звонить.
- Если указать слишком большое значение, то оператор может прервать звонок до истечения указанного времени.

### Таймаут дозвона

Обычно проходит от 5 до 10 секунд между началом набора номера и моментом, когда вызываемый телефон начинает звонить. По умолчанию, интеграция пытается установить соединение в течение 20 секунд. Это время можно изменить с помощью параметра `dial_timeout_sec`.

### Проверка связи с модемом (keepalive)

Некоторые модемы перестают отвечать на AT-команды после нескольких дней простоя. Интеграция может периодически отправлять модему команду `AT`, чтобы зависание обнаруживалось заранее, а не в момент звонка. Интервал в минутах задаётся параметром `keepalive_interval_min` (по умолчанию выключено):

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-HUAWEI_Technology_HUAWEI_Mobile-if01-port0
    keepalive_interval_min: 30
```

Примечания:
- Проверка пропускается, если в этот момент идёт звонок или отправка СМС; звонки и СМС, начатые во время проверки, дожидаются её окончания.
- При включённых отладочных логах каждая проверка записывает регистрацию в сети (`AT+CREG?`), уровень сигнала (`AT+CSQ`) и, для модемов Huawei, `AT^SYSINFO`.
- Если модем не отвечает, публикуется событие `gsm_call_modem_unresponsive` (см. [События](#события)).

## Использование на практике

Подробная статья по настройке охранной сигнализации с дозвоном: [Сигнализация в Home Assistant с функцией дозвона на телефон](https://mansmarthome.info/posts/okhrana-doma/sighnalizatsiia-v-home-assistant-s-funktsiiei-dozvona-na-tieliefon/?utm_source=github&utm_medium=referral&utm_campaign=gsm).

В статье показано, как создать автоматизацию, которая при обнаружении движения совершает звонок и отправляет снимок с камеры.

## События

Компонент публикует событие `gsm_call_ended` с указанием того, был сброшен звонок или принят. Таким образом, например, можно выключить сигнализацию, если вызываемый абонент отклонил звонок:

```yaml
automation:
  - alias: "Disarm the security alarm when a call is declined"
    triggers:
      - trigger: event
        event_type: gsm_call_ended
        event_data:
          reason: "declined"
    actions:
      - action: alarm_control_panel.alarm_disarm
        target:
          entity_id: alarm_control_panel.security
```

`reason` может содержать следующие значения:
- `not_answered` — нет ответа;
- `declined` — звонок сброшен;
- `answered` — абонент поднял трубку.

Также помимо `reason` можно указать `phone_number` для фильтрации по номеру телефона. Все возможные свойства доступны в [панели разработчика](https://my.home-assistant.io/create-link/?redirect=developer_events).

Если включена [проверка связи](#проверка-связи-с-модемом-keepalive) и модем не ответил, публикуется событие `gsm_call_modem_unresponsive` с путём к модему в `device`. Его можно использовать для уведомления или перезапуска модема:

```yaml
automation:
  - alias: "Notify when the GSM modem is stuck"
    triggers:
      - trigger: event
        event_type: gsm_call_modem_unresponsive
    actions:
      - action: persistent_notification.create
        data:
          message: "GSM modem {{ trigger.event.data.device }} is not responding"
```

## Поддержка СМС

В будущем рассматривается добавление отправки и, возможно, получения СМС-сообщений. Это позволит использовать модем не только для звонков, но и для текстовых уведомлений.

Однако реализация этой функции требует значительных усилий, и предварительно хотелось бы оценить интерес сообщества.

**Если эта функция вам нужна:**
- Поставьте 👍 в [соответствующей issue на GitHub](https://github.com/black-roland/homeassistant-gsm-call/issues/17);
- Оставьте комментарий с описанием ваших сценариев использования.

Ваш отклик поможет понять, насколько востребована эта функция и стоит ли сфокусироваться на её реализации в первую очередь.

*Примечание: интеграция является опенсорсной. Если вы готовы помочь в разработке — дайте знать в комментариях к issue или ознакомьтесь с [рекомендациями по внесению изменений](./CONTRIBUTING.md).*

## Поиск и устранение проблем

Для начала, пожалуйста, включите отладочные логи в `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.gsm_call: debug
```

После перезапуска Home Assistant, проверьте логи в разделе *Настройки* → *Система* → *Журнал* (или используйте [эту ссылку](https://my.home-assistant.io/redirect/logs/)).

### Модемы ZTE

На некоторых модемах от ZTE дозвон работает только после предварительной отправки команды `AT%icscall=1,0`. Попробуйте указать `hardware: zte`, если с конфигурацией по умолчанию дозвон не работает:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-ZTE_MF192_D536C4624C61DC91XXXXXXXXXXXXXXXXXXXXXXXX-if00
    hardware: zte
```

### Модемы на базе GTM382

Для модемов Globetrotter HSUPA и других на базе чипа GTM382 укажите `hardware: gtm382`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/ttyHS6
    hardware: gtm382
```

### ATD/ATDT (команды для набора номера)

Большинство модемов должны работать со стандартными настройками, но если возникли проблемы, вашему модему может потребоваться особая команда набора номера. Для проверки попробуйте указать `hardware: atdt`:

```yaml
notify:
  - name: call
    platform: gsm_call
    device: /dev/serial/by-id/usb-Obscure_Hardware-if01-port0
    hardware: atdt
```

## Спасибо

Интеграция оказалась полезной? Хотите сказать спасибо? Кофе автору — ваша благодарность. <kbd>[☕ На кофе](https://mansmarthome.info/donate/?utm_source=github&utm_medium=referral&utm_campaign=gsm#%D1%81%D0%B8%D1%81%D1%82%D0%B5%D0%BC%D0%B0-%D0%B1%D1%8B%D1%81%D1%82%D1%80%D1%8B%D1%85-%D0%BF%D0%BB%D0%B0%D1%82%D0%B5%D0%B6%D0%B5%D0%B9)</kbd>

Большое спасибо всем, кто меня поддерживает:

<p>
  <img src="https://github.com/user-attachments/assets/57f36b9d-118a-47b7-9ac3-77319bd6d7e3" height="100px" alt="Аноним" />
  <img src="https://github.com/user-attachments/assets/107d303c-e052-4b19-bf41-4f8ef675c6ed" height="100px" alt="ivanik7" />
</p>

## Поддерживаемое железо

В целом эта интеграция [должна быть совместима с модемами, указанными здесь](https://wammu.eu/phones/).

Протестировано на:
- Huawei E1550 (определяется в системе как Huawei E161/E169/E620/E800).
- Huawei E171.
- Huawei E3531 (необходимо разблокировать с помощью [этого руководства](http://blog.asiantuntijakaveri.fi/2015/07/convert-huawei-e3372h-153-from.html)).
- ZTE MF192 с указанием `hardware: zte` в конфигурации.
- Globetrotter HSUPA (`hardware: gtm382`).

**Хотите добавить поддержку своего модема?** Ознакомьтесь с [рекомендациями по внесению изменений](CONTRIBUTING.md#добавление-поддержки-новых-модемов), чтобы узнать, как вы можете помочь!
