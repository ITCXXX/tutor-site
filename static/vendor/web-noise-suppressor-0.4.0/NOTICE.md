# Шумодав голоса: откуда эти файлы

Используется в голосовой связи доски (`static/board/board.js`, раздел «Шумодав»):
голос перед отправкой собеседникам проходит через нейросеть RNNoise прямо в
браузере говорящего.

## Источник

- Пакет `@sapphi-red/web-noise-suppressor`, версия **0.4.0**, из официального
  каталога npm: https://registry.npmjs.org/@sapphi-red/web-noise-suppressor/-/web-noise-suppressor-0.4.0.tgz
- Контрольная сумма архива (SHA-1, совпадает с указанной в каталоге):
  `951bd0194ed1e4702bc0d7475efaa48df2c84c96`
- Исходный код: https://github.com/sapphi-red/web-noise-suppressor
- Добавлено в проект 15.09.2026 с разрешения владельца сайта.

## Что взято и что изменено

| Здесь | В пакете | Изменение |
|-------|----------|-----------|
| `rnnoise-worklet.js` | `dist/rnnoise/workletProcessor.js` | удалена последняя строка `//# sourceMappingURL=…` (см. `static/vendor/README.md`), файл переименован |
| `rnnoise.wasm` | `dist/rnnoise.wasm` | без изменений |
| `rnnoise_simd.wasm` | `dist/rnnoise_simd.wasm` | без изменений |
| `LICENSE` | `LICENSE` | без изменений |
| `LICENSE-rnnoise-wasm-Apache-2.0.txt` | — | полный текст Apache License 2.0 для кода rnnoise-wasm внутри `rnnoise-worklet.js` (в пакете его не было) |

Класс `RnnoiseWorkletNode` и проверка поддержки SIMD из `dist/index.js` (около
15 строк) переписаны прямо в `board.js`: отдельным файлом их не подключаем.

## Лицензии

1. **web-noise-suppressor** — MIT, © 2022 翠 / green. Полный текст — в `LICENSE`.
2. **rnnoise-wasm** (сборка RNNoise в WebAssembly, на которой построен пакет) —
   Apache License 2.0, © Takeru Ohta и Shiguredo Inc.:
   https://github.com/shiguredo/rnnoise-wasm . В самом `rnnoise-worklet.js`
   указано: «@shiguredo/rnnoise-wasm, версия 2022.2.0, автор Shiguredo Inc.,
   лицензия Apache-2.0». Полный текст лицензии — в `LICENSE-rnnoise-wasm-Apache-2.0.txt`.
3. **RNNoise** (сама нейросеть, внутри `.wasm`) — лицензия BSD из 3 пунктов.
   Нейросеть в `.wasm` собрана не из основного репозитория xiph/rnnoise, а из
   форка https://github.com/shiguredo/rnnoise, метка 2022.1.0 (её берёт скрипт
   сборки rnnoise-wasm 2022.2.0). Текст — файл `COPYING` с этой метки:

```
Copyright (c) 2021, Shiguredo Inc.
Copyright (c) 2017, Mozilla
Copyright (c) 2007-2017, Jean-Marc Valin
Copyright (c) 2005-2017, Xiph.Org Foundation
Copyright (c) 2003-2004, Mark Borgerding

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

- Redistributions of source code must retain the above copyright
notice, this list of conditions and the following disclaimer.

- Redistributions in binary form must reproduce the above copyright
notice, this list of conditions and the following disclaimer in the
documentation and/or other materials provided with the distribution.

- Neither the name of the Xiph.Org Foundation nor the names of its
contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION
OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Обновление

Новую версию пакета класть в новую папку с номером версии, снова убрать строку
`sourceMappingURL` и поправить три пути в словаре `ШУМОДАВ_ФАЙЛЫ`
(`board/views.py`). Старую папку удалять только после этого и после
collectstatic: если путь не найдётся, шумодав молча станет «недоступен» у всех.
Имя процессора внутри ворклета (`@sapphi-red/web-noise-suppressor/rnnoise`) и
параметры `processorOptions` сверить с `dist/index.js` новой версии.
