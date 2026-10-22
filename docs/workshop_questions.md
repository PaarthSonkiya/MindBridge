# Questions for the Qualcomm technical workshop (Fri 23 Oct 2026, 17:00–18:00 Vietnam / 18:00–19:00 Singapore)

## For the organisers (rules)

1. Is the hidden 1,000-sentence test set fed to our system as **audio or text**? If audio, who recorded
   it (native speakers, TTS) and at what sample rate? How do we receive it at judging time?
2. How is translation quality scored: BLEU, COMET, chrF, human rating, or a mix? Is it per direction
   (VI→EN and EN→VI separately)?
3. For self-verification (7.2), which exact device and OS image will judges use? Is Ubuntu 24.04 on
   RB3 Gen 2 acceptable, and will Docker be available?
4. Can teams outside Vietnam (we are in Singapore) test on our own RB3 Gen 2 and submit, and are the
   Field-Testing round (28 Nov) and Final (5 Dec) in person only?
5. Which language pairs will Field-Testing require on top of the one we register?
6. Does a non-commercial model licence (NLLB-200, CC-BY-NC) cause any problem?

## For Qualcomm (technical)

1. On **QCS6490 / HTP v68**, which QAIRT version should AI Hub target so that context binaries load with
   `onnxruntime-qnn` 2.7.0 (QAIRT 2.51)? Should we fetch `precompiled_qnn_onnx` or `qnn_context_binary`?
2. On Ubuntu 24.04 for RB3 Gen 2, which packages enable FastRPC/CDSP for QNN HTP (e.g. from
   `ppa:ubuntu-qcom-iot/qcom-ppa`)? What is the right `ADSP_LIBRARY_PATH`?
3. Is there a supported path to run an encoder–decoder translation model (NLLB / Marian) on the HTP —
   e.g. encoder on NPU, decoder on CPU? Any AI Hub examples?
4. Any plans for Genie / small LLM support on QCS6490 (HTP v68), or is IQ-8275 the minimum for LLMs?
5. Is the Qualcomm **Voice AI SDK** runtime (listed for Whisper on AI Hub) available for Linux on RB3 Gen 2,
   and would you recommend it over ORT-QNN for streaming ASR?
6. Best practice for keeping the HTP warm (performance mode `burst` vs `sustained_high_performance`)
   for bursty push-to-talk workloads, and how to read NPU utilisation on device?
