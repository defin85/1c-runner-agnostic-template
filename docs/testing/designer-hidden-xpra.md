# 1C Designer Hidden GUI Through `xpra`

Этот документ описывает template-managed operator-local contour, когда нужно открыть `1cv8 DESIGNER` внутри WSL без проброса окна на host `DISPLAY`, но с возможностью визуально проверять и осторожно редактировать ordinary/binary forms.

## Когда использовать

- Нужно просматривать или править формы через `Designer`, но не хочется открывать окно на host-машине.
- Нужна hidden GUI automation внутри WSL для `xdotool` и скриншотов.
- Нужно подтвердить, что binary form editor реально рендерится в Linux hidden-сессии.

## Что уже подтверждено

- `xpra + openbox` рендерит главное окно `Designer` корректно внутри hidden X session.
- Pure `Xvfb` без `xpra/openbox` для этого контура недостаточен: окно есть, но содержимое рендерится ненадёжно.
- Проверенный маршрут:
  - открыть конфигурацию;
  - найти metadata object через configuration search;
  - открыть data processor;
  - открыть страницу `Forms`;
  - открыть binary form editor `ФормаЗагрузки`.

## Preflight

Проверьте наличие инструментов:

```bash
pacman -Q xpra openbox xdotool imagemagick xorg-xwininfo xorg-xprop
```

Если `/tmp/.X11-unix` в WSL смонтирован как read-only `tmpfs` без sticky bit, `xpra`/`Xvfb` contour нужно запускать поверх временного overmount:

```bash
mount | rg '/tmp/.X11-unix'
ls -ld /tmp/.X11-unix
sudo mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp/.X11-unix
```

## Поднять hidden desktop

Канонический draft-контур:

```bash
xpra start-desktop :102 \
  --daemon=yes \
  --attach=no \
  --mdns=no \
  --systemd-run=no \
  --start-child=openbox \
  --exit-with-children=no \
  --html=off \
  --xvfb='Xvfb -screen 0 1440x900x24 -nolisten tcp -noreset -auth $XAUTHORITY' \
  --log-file=xpra-102.log
```

Проверка:

```bash
xpra list
```

## Запустить `Designer`

Подставьте свой installed platform path, infobase и учётные данные:

```bash
ONEC_DESIGNER=/opt/1cv8/x86_64/8.3.27.1859/1cv8
DISPLAY=:102 LD_PRELOAD='/usr/lib/libstdc++.so.6:/usr/lib/libgcc_s.so.1' \
  "$ONEC_DESIGNER" DESIGNER \
  /S 'host:port/infobase' \
  /WA- \
  /N 'user' \
  /P 'password'
```

Для первичной проверки окна:

```bash
env DISPLAY=:102 xwininfo -root -tree
```

## Делать readable screenshots

После каждого значимого GUI-шага снимайте скриншот root window:

```bash
env DISPLAY=:102 bash -lc 'xwd -silent -root -out /tmp/designer-root.xwd && magick /tmp/designer-root.xwd /tmp/designer-root.png'
```

Если popup menu или другой transient editor открылся отдельным X window, сначала найдите его id:

```bash
env DISPLAY=:102 xwininfo -root -tree
```

Потом снимите именно это окно:

```bash
env DISPLAY=:102 bash -lc 'xwd -silent -id 0xWINDOW_ID -out /tmp/window.xwd && magick /tmp/window.xwd /tmp/window.png'
```

## Проверенный navigation pattern

Этот маршрут уже подтверждён на `1440x900` в hidden `xpra` session:

1. В главном окне `Designer` откройте `Configuration -> Open configuration`.
2. В окне конфигурации используйте configuration search: `Ctrl+Alt+M`.
3. Введите search term, например `I584`.
4. В отфильтрованном дереве выберите нужный metadata object стрелками и нажмите `Enter`.
5. В редакторе объекта откройте страницу `Forms`.
6. На контейнере `Forms` нажмите `Right`, чтобы показать дочерние формы.
7. Выберите нужную форму стрелкой `Down` и нажмите `Enter`.

Подтверждённый пример:

- `I584_ПоступлениеАгентскихТоваровИУслуг`
- `Forms`
- `ФормаЗагрузки`

## Правила

- По умолчанию используйте hidden `DISPLAY`, а не `:0`.
- Не возвращайтесь к bare `Xvfb`, если `xpra` уже доступен.
- После каждого существенного действия снимайте скриншот; не работайте вслепую длинными сериями.
- Для navigation после configuration search предпочитайте клавиатуру, а не координатные клики.
- Сохраняйте изменения в `Designer` только если пользователь явно попросил редактирование.

## Known Limits

- Arch package `xpra` может не включать HTML5 web root. Это не блокер для WSL-only automation, но browser attach может быть недоступен.
- Popup menus и transient windows могут жить отдельными X windows; root screenshot не всегда показывает их корректно.
- Координатные клики сильно зависят от разрешения и набора toolbars. Для repeatable automation устойчивее клавиатурный маршрут после поиска.

## Cleanup

Если были правки, сначала закройте `Designer` штатно и обработайте save prompts. После этого:

```bash
xpra stop :102
sudo umount /tmp/.X11-unix
```

## Future Repo-Owned Wrapper Draft

Этот runbook намеренно остаётся doc-first draft. В текущем template source repo его нельзя публиковать как активный `.agents/skills/*`, потому что project-scoped skills здесь обязаны быть thin wrapper-ами над repo-owned scripts.

Минимальный путь к promotion:

1. Добавить repo-owned wrapper, например `./scripts/gui/start-hidden-designer-xpra.sh`.
2. Вынести в script deterministic шаги:
   - overmount `/tmp/.X11-unix`;
   - старт `xpra + openbox`;
   - запись session id, `DISPLAY`, log path и PID artifacts;
   - optional `Designer` launch inside the same `DISPLAY`.
3. После этого добавить thin skill facade `1c-designer-hidden-xpra`, который будет ссылаться на script contract, а не дублировать GUI runtime logic inline.
