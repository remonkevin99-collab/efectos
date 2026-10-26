# Los modelos de esta carpeta

`instalar.sh` (o `instalar.ps1`) baja aquí dos modelos oficiales de Google para MediaPipe, sin cambiarlos:

| Archivo | Para qué | De dónde |
|---|---|---|
| `selfie_segmenter.tflite` | separar a la persona del fondo (la máscara) | https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite |
| `blaze_face_short_range.tflite` | encontrar la cara | https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite |

No son parte del código de este repositorio (que es MIT): son de Google y se distribuyen con su licencia, la Apache 2.0.

```
Copyright 2023 The MediaPipe Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

Más sobre los modelos (sus fichas, con el uso previsto y sus límites): https://ai.google.dev/edge/mediapipe/solutions/vision/image_segmenter
y https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector
