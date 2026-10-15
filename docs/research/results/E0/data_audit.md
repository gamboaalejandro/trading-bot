# E0 — Data audit

Generated 2026-10-15 20:50 UTC. Market: **spot+futures**. Trials: none (not a trial). Holdout: closed.

## Warnings

- **Survivorship bias.** Every symbol of the universe is still listed in 2026; delisted coins (LUNA, FTT, SRM and others) are missing. Conclusions focus on BTC/ETH and every basket result carries this warning (PLAN §5.1).
- **Funding not verified.** The local funding is sampled at 00/08/16 UTC and may be the predicted rate, not the settled one; symbols moved to 4h/1h intervals are under-counted. P&L that depends on funding is UNVERIFIED until checked against `/fapi/v1/fundingRate` and `/fapi/v1/fundingInfo` (PLAN §2.7, §5.2.3, §8). BNBUSDT funding is excluded.
- Published figures (papers, debate) are not targets; only these OOS numbers count.

## Data provenance

- Harness git sha: `278307a223716d9af6a96964a4f7c13aab41ca8e`
- Data commits (upstream sources): futures `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, funding `735eb87ffafb5c431162d7fec0d9bb3bf88d6d47`, spot `4d33a56f2b3930376fc778522770c6e84855be7e`
- Manifest digest: `4642f4faa57fb13455c55c65d20840c8b5a82150c279df98d409179b0a9b3f24`

<details><summary>CSV SHA-256 (130 files)</summary>

- `funding/ADAUSDT.csv`: `64411b95e03c131f132d153f844037612a726ef18c988180a912446e0b669eff`
- `funding/APTUSDT.csv`: `4ecc3579ce5113a4b5fc4d918dd5c7fce9dfc963057b017762da9c73e48bbdca`
- `funding/ARBUSDT.csv`: `bc4f0be38685497ec1656a25c8e5ba152c562ce25594b1ba5aa140bd080f09dd`
- `funding/AVAXUSDT.csv`: `ff110bfb29dd6d60d6058cf0ed6da5d1489985f52ccde94454243484280e3ff5`
- `funding/BCHUSDT.csv`: `37fadd11849dc5c13d686d25e5aceae4dcdf2787d72bbde37f521eba83f787fd`
- `funding/BNBUSDT.csv`: `3688e7af69dfe174358a5ea2c34c750e5d5f477583cd3bca227e2f530d32a6d0`
- `funding/BTCUSDT.csv`: `bed68ff8e480c6dc987dff31080cff2c612fa292bb33faa27db15b8146fd8b4a`
- `funding/DOGEUSDT.csv`: `a23583aeca171b437853fb2889d7f6f470b9d7afa5ff16d0ebb864316ffcedf0`
- `funding/DOTUSDT.csv`: `c524bd82553269714d0ddb0c033e284f6d5cfa11bdf56fa074fb71fe536b5ffa`
- `funding/ETHUSDT.csv`: `16542a31bca233c366d64dd054b5c9fe313362943db77d230aeacb4e0d2138fd`
- `funding/LINKUSDT.csv`: `970d7504d12f8d9c3426f48766fd42dd1300b100ebdf855c032888883e4cb51b`
- `funding/LTCUSDT.csv`: `d3e1ee5dcf315930c51c5bef1a64f58475a0e2b54e1d6bb4e7c76a57f2b10ef2`
- `funding/NEARUSDT.csv`: `524daf275aa2b990a0f798aff3697095e1d7350ce5426ab1694ef01028d1bdd3`
- `funding/OPUSDT.csv`: `74ba7bd51b513ce3e342de0001f6d75f26dc418765fa5992a0b7c8a11d39b3ee`
- `funding/SOLUSDT.csv`: `bbc5852b0f57c0804ee51d1508f22f0fcd49356a77bc27ffddd858596ec7d830`
- `funding/SUIUSDT.csv`: `6cffd42c6512568387fa9c9592218349888ed1fb006560b056b5e0726820a923`
- `funding/TRXUSDT.csv`: `b2fa7ed917eb7356533c7a33741ccca25b9116f5b2a8622e6e674c3c7f8a5d35`
- `funding/XRPUSDT.csv`: `05071ac0c27a260619896a1497cfd691aa5ef2cd856dbb84c837e229fd8341cc`
- `futures/ADAUSDT_15m.csv`: `473e7f17ddcf0db52fc08be2c12d959dc8de085aa5d0b4044e7f997f71b9b29c`
- `futures/ADAUSDT_1d.csv`: `80135a2a0743772a0c8cc7d0f564305e033b139c4b69f3f066cad01b921727b2`
- `futures/ADAUSDT_1h.csv`: `0de0c16b29e6e8cbe14464e053d369f2d1b28c47f9a28fec07a97c5c16b6e24c`
- `futures/ADAUSDT_4h.csv`: `eae979a4ab13108b1b09f9c46bc316d066070ef481fa4f313cad1e128206ac76`
- `futures/APTUSDT_15m.csv`: `6881d5797495a3bc23f7252d7d70816e4bdfae275325b753c50c4970717e0425`
- `futures/APTUSDT_1d.csv`: `927768f90fbc2b49b103fdaacc94f4c6021128467f83fa3a5fcd30c153e0be0e`
- `futures/APTUSDT_1h.csv`: `a490a7480e4fe11e27f9991eda4e48b7d19433baa3425b70611b8e5dfb9b5067`
- `futures/APTUSDT_4h.csv`: `3c68afcae3821876fb49e79a001c4214bd7cbbf3211f026a8abe24f15a029b14`
- `futures/ARBUSDT_15m.csv`: `70f309441c04e17799ed2cd6da1fb0d1af91845d9e3ad8627b7fe436e186aeed`
- `futures/ARBUSDT_1d.csv`: `5e18d9fcb03bb6bffc7d0988e7eaa2d3dfdd1991a8931db87ff70ac9d7f94f46`
- `futures/ARBUSDT_1h.csv`: `39f4a35e5d8c7b1e5c2012469686361cca247c0652e906f074b38aca5e2c59bb`
- `futures/ARBUSDT_4h.csv`: `18c82db74245b76464f2b570e0938407e2a93377bed69c6d85656c3143613f36`
- `futures/AVAXUSDT_15m.csv`: `42b69174b12e60aeff96709a36e89c00a49859b9a1b934234481d726f9766f75`
- `futures/AVAXUSDT_1d.csv`: `fa9476c6cbd92a8ffee5f10dd40df6928fafc6b7204904822f117f6a494543a3`
- `futures/AVAXUSDT_1h.csv`: `397d88b37dcf8b44096abee1782f4117bd4f70fb150b36cff8ceec431146c004`
- `futures/AVAXUSDT_4h.csv`: `8b030068952dd864b080fed4f5a183f1f696b47a625ba53ae1a61d5d243d0c00`
- `futures/BCHUSDT_15m.csv`: `a09ce4650d59284e35a31cee8af7e36091793900092192c0fb1b7decf947e2f1`
- `futures/BCHUSDT_1d.csv`: `ebcde04df1cfe03d31cb7aecd9ea44eb77b44bee98a0bb080787c774968ebfc7`
- `futures/BCHUSDT_1h.csv`: `eca9c84672161f20f9448df42c57ac2766cff71ab36fcc15f817659cf1626d05`
- `futures/BCHUSDT_4h.csv`: `ef2e77b91c85be9ebc3649867bf0c51140aa80dbe59b7f94ee080e2f7fafad7a`
- `futures/BNBUSDT_15m.csv`: `0403aec61d5f00c819da50f3abab2da45e12f3e76fe72db83fdb084216b3392f`
- `futures/BNBUSDT_1d.csv`: `a1534b656035fb24ed250d436ffcadb481f18df9c82e262d208eb12f30d970b1`
- `futures/BNBUSDT_1h.csv`: `9084a76a6d77b20b124619e4ef660e149d3af090515c52af05442412b4f2dfe1`
- `futures/BNBUSDT_4h.csv`: `45aa933e5eb8e92748e2ba8a326be89f2422d7977cb0f72a2beef3a155b93cdc`
- `futures/BTCUSDT_15m.csv`: `6d3e660baec193271d9d6391e1a453bca16a1457271cba9187dca8118ce8ca1e`
- `futures/BTCUSDT_1d.csv`: `9a28da68ff94306ad603e2d32729bfe472cdcd9b99bff2fea3ec916bd6879d7e`
- `futures/BTCUSDT_1h.csv`: `e8770e39f739e22aa0141128eb119d8c199a28ca85a8d49645fab62e31aee2c8`
- `futures/BTCUSDT_4h.csv`: `4c67ae1dde25cfa9dc451b9b16622dff4910729949e03bfe19b9f19efe108b4a`
- `futures/DOGEUSDT_15m.csv`: `60291aa252e96af20143489fe54b6cec20d2726b71eacd6e4d908f92e877174b`
- `futures/DOGEUSDT_1d.csv`: `01431fd6d06b3035fd044c20d222270bcbe56d19e26c962ff1a3e9241736ac07`
- `futures/DOGEUSDT_1h.csv`: `d832367680be5efa4295192e7204582214ead633943a4f8467b0838193568eef`
- `futures/DOGEUSDT_4h.csv`: `05397fa3613f872e0e39985466033666327a554792cef7beff1b918306e2f544`
- `futures/DOTUSDT_15m.csv`: `d1c52b5a8c6a4ff996d45026f14f8903cb5bd3e23304b751d2f45d93e8480873`
- `futures/DOTUSDT_1d.csv`: `29af13c1b42b2d1de36dc505a45bbdbfd558c7d35231212ad94ae5ef59ddc612`
- `futures/DOTUSDT_1h.csv`: `caac7d6bd77199900c6a6f47940f086e4d9e4aeffbf2f7c708665b10365e6e90`
- `futures/DOTUSDT_4h.csv`: `18ee78f2e31311a6987dee34495f495073a0abf84daad4917533f425f62187e0`
- `futures/ETHUSDT_15m.csv`: `99c9e280add18988f5d8d51f28d195e75472aedf4da3fd13ebbd47f586b13f08`
- `futures/ETHUSDT_1d.csv`: `5e888c4bdc2e31fb5afc212623248de855984db98b1e1adcb53515f50ea12662`
- `futures/ETHUSDT_1h.csv`: `1294b1fa442cdf6534d7da1f24aeb1258827be5cae570b21151dd94e72b9d8a1`
- `futures/ETHUSDT_4h.csv`: `00ea44b05550d7b1c611592fc9e207c35c4793649b2d7dc77a06cd5efc1aded5`
- `futures/LINKUSDT_15m.csv`: `ebffe8c2f0b6c5e9aca2f23830e500e2e46282e148afad33bb85dbe4335fb1b2`
- `futures/LINKUSDT_1d.csv`: `5a61bf6272a2b2b682da1f15b25c37d7b6cdfe79ed44cd2123fe8edcce22fc4d`
- `futures/LINKUSDT_1h.csv`: `3f00255f59b41b22d694654da4c96fe4b8b1a18afef93353565a5edcf7f2f069`
- `futures/LINKUSDT_4h.csv`: `d7344429ad47da520ca0481037c934473f60e9cbc99103fe719e892eccce50f3`
- `futures/LTCUSDT_15m.csv`: `09fd1b61ca1f15ad9455105d4a775504a6972a0a2e2a9b22552190c784004e05`
- `futures/LTCUSDT_1d.csv`: `75bfc1c9afba1512cfcc56d77c3773a2ed2ad33bb22f7ae9fa1fa6f0d9122320`
- `futures/LTCUSDT_1h.csv`: `e0b4d8af58050314daebe38eb264049441a0e48f596aa37ef41b4670b5d81c71`
- `futures/LTCUSDT_4h.csv`: `7575dcfb6bc40fe4e1deebf142fcbf8da13914696f19897fcf16f8f952599487`
- `futures/NEARUSDT_15m.csv`: `94339cadca57c5dc01a6b67ed3951ca69317c9358ec15c9a499b2dd4a8a87ba5`
- `futures/NEARUSDT_1d.csv`: `707d2e09f73e0dfbe0c428ca13c77d28db16f2d71d57d8a28b8ee5ce65999c37`
- `futures/NEARUSDT_1h.csv`: `2d5da1a1f5ef5faafdf1b9530e3725aa5ad07f6927c34502a14126485564422b`
- `futures/NEARUSDT_4h.csv`: `1a6ee445b1342542b83184c1f1789bba574de385bb6cdc8a09316190fc0d9aaa`
- `futures/OPUSDT_15m.csv`: `7f71ff377734999f999bb17d30d53394cef2a7e913e057d5971dfd66201592c5`
- `futures/OPUSDT_1d.csv`: `6b77bf84924629e3826f43dcd09b2240b13cae5a65d6e741ee3f561729d6f1df`
- `futures/OPUSDT_1h.csv`: `effd7f58f0b20eec0e6206fec2e2bfb7d06375e5046fa41b8188742d9f019aff`
- `futures/OPUSDT_4h.csv`: `5f84d19f1812cff42e7db9d179c42b8a15f03a742494e386c4589fb677269e20`
- `futures/SOLUSDT_15m.csv`: `7df26646a96a60f0354c6c2ec5dbaffc63e0e0f0b63a1026df49046f4024d99d`
- `futures/SOLUSDT_1d.csv`: `6e2942eb6e7057b1ccc9cd1e232c42d69a0de2387432c9cf8ca10c58a8e9a3d8`
- `futures/SOLUSDT_1h.csv`: `7eb04165739ec77093953f89010182c57bd1875ef0a4b31512c27f62f78a9728`
- `futures/SOLUSDT_4h.csv`: `d67f0449dfea47ae931d5079b0335611e82e6beff2b24e47a4cef223b22c2878`
- `futures/SUIUSDT_15m.csv`: `19f0263c1bc442378df1978853f3763a8bbb96e43e3b47ec3de1de0f63f87370`
- `futures/SUIUSDT_1d.csv`: `e71a8b64a32d16bff4e347c5d8b05a0481e9616b20b8866edb56d9a355bb7a95`
- `futures/SUIUSDT_1h.csv`: `48bfbcd09bb7afdb966ddce7cca9d2cd059f0af2f0cef38ad69d2657055bbcd3`
- `futures/SUIUSDT_4h.csv`: `65fd3f2867a9b1c2c9fcc48800febf5faa5acc7bf09fcd4cbe1b9d0e2fbddc15`
- `futures/TRXUSDT_15m.csv`: `24c99404447e31df2900221338a8bfe101aea20d5fe0ee090dc79d78a2ee5f16`
- `futures/TRXUSDT_1d.csv`: `1f0d03ef425dbb6e8b31d1f5828ead744238e325c9b28b5cfa0031cbf746580d`
- `futures/TRXUSDT_1h.csv`: `b53f1f5695611bfcbb531b90af9290a67127cd0d975f031d92928f5faa7b2fdd`
- `futures/TRXUSDT_4h.csv`: `761dfa00fc88f92f027f819c5d3b20d897e334b84e10ef523db3bf0713e5264c`
- `futures/XRPUSDT_15m.csv`: `052a4cf5713610808aaab4ea50bc5b06962917fb6a38c81250351193fd6b2796`
- `futures/XRPUSDT_1d.csv`: `fb6f6533b18c91ea5e0494ab3659f4f849980ae32fc9c3cb2ae59f0d7baf03e7`
- `futures/XRPUSDT_1h.csv`: `8ebc6897a5ed995ab2e1f00088902711264cec8fe0cb4349384e322d0705ea5d`
- `futures/XRPUSDT_4h.csv`: `abd05de2a064874f020a2a519fdb907b351bd9c0f5de34c5508786c60da832f8`
- `spot/ADAUSDT_15m.csv`: `284ad847bddd4faaaefdcfd60daa9f23532f6c8656d8b00c2432359ec9dbb3d8`
- `spot/ADAUSDT_1d.csv`: `b3acd5f72498d72449a4692eedf9963092827fd62345db3c510dafa68362c64b`
- `spot/ADAUSDT_1h.csv`: `b19426d86254955672be37230aa30405b407b6cdafbad8371ac8a64386112fd0`
- `spot/ADAUSDT_4h.csv`: `e086f9dcae40036885c071695f9be5a27d337590ba0993d6e1ae0493cd808720`
- `spot/AVAXUSDT_15m.csv`: `5dbadb2aef799771ec8e06091c98324fe44a737646280039cdeab0c0f5cf4b82`
- `spot/AVAXUSDT_1d.csv`: `2b117fb6848226ecec76a3ad94825e9ffa9a75f87f5be9aefb763ae611b475a7`
- `spot/AVAXUSDT_1h.csv`: `8b262cf77d2b25d4705b88df6b70ca4e07ed7de79be6a870e585869653c7ddd0`
- `spot/AVAXUSDT_4h.csv`: `4c7a5fcb5a9632ab4ab801899b2e994edac4354ce681e5ef5da122c49d3c3e1d`
- `spot/BNBUSDT_15m.csv`: `b92c943e88d83a733851241eec9256ec906d9d30a14f2f51c5ad45cc965bd18d`
- `spot/BNBUSDT_1d.csv`: `5d47c41feafa4f8abfef746fc443904a9a63bd55f5899015df3ada5192cc1108`
- `spot/BNBUSDT_1h.csv`: `1f4b45deed411127f101447dee8676fa76036409674e4bcea6112c53f0bba602`
- `spot/BNBUSDT_4h.csv`: `58cabcedad8302e2ffa0de11052851fd0b0186191954812b1f4c25004ff0fe63`
- `spot/BTCUSDT_15m.csv`: `0b7bc5c0ff381fe8c340024557272970c6863db990b2064dbb805ef0f399dbbe`
- `spot/BTCUSDT_1d.csv`: `a8b34b72f3e9434e02929658d495db6dd872789eff6faf8c89282ec56c6807d0`
- `spot/BTCUSDT_1h.csv`: `ed03b747970a479272c62b0f6bdf4990a88c1501d8938533a15cae376a567814`
- `spot/BTCUSDT_4h.csv`: `3fdca05b00339f1775998005dbcf0969aaca785f7205b57707463bb89df92b5c`
- `spot/DOGEUSDT_15m.csv`: `e7c315aa8cefccb9c5a58b0acb0e6d6138477846cc63dbff52bb4ae266bba8ef`
- `spot/DOGEUSDT_1d.csv`: `703025b51ebd1cb11b4ba412031b42c7067a45283f2789cc3a9ccb9362dda664`
- `spot/DOGEUSDT_1h.csv`: `8f0a42a235f3fe4b508319e89d036571be89c175a9adb141e9bc38b68f1ef5bc`
- `spot/DOGEUSDT_4h.csv`: `7725e5aad3eada58191e515b4183aaa5f0a3f96391dabbbac529c7f8ff1659b7`
- `spot/DOTUSDT_15m.csv`: `a4ea441b88b350420fdf24920d87a667abd99b89bbd55617478e73cb23bdbc6a`
- `spot/DOTUSDT_1d.csv`: `fcebf79b88207de5bb255d7aee72659a94f02d5841291f39d15d9c9ef68393e8`
- `spot/DOTUSDT_1h.csv`: `ab59a9aa86d1e97ce97a6d68f65209077deceeb2a9f8d8abccddbc26d54dfd53`
- `spot/DOTUSDT_4h.csv`: `a1cab600c72b7ee7539ed9a93d4723955c2047b109676db40ff0c4d311c2876d`
- `spot/ETHUSDT_15m.csv`: `0ccadf3f40dba9e0549d75160d59a25dfd0fa256c15849de646a7d458902c350`
- `spot/ETHUSDT_1d.csv`: `647b97d96833b426484e5674db3f2d6ee149dffa32f21aec927fad82ccfa84c7`
- `spot/ETHUSDT_1h.csv`: `c983a31432974a3116729fc8a044e86b276b160ade0eb08931c85b4817180701`
- `spot/ETHUSDT_4h.csv`: `efa2d9429c2c4a0e0efc727d3b937b3d44880db9d493578144a108818f1a10b7`
- `spot/LINKUSDT_15m.csv`: `73c93a3040d09dc78e06f9142e9e523664a48c02fc7d147e7cfcc367f5cefba7`
- `spot/LINKUSDT_1d.csv`: `45b75b4886fed76a1430b00c9a29b1cc6c0bc50600c0fe7825dc11514267b1df`
- `spot/LINKUSDT_1h.csv`: `2f4e8d668d680783a4e772dbbd6d8bd99af8ed6e5cb6c4890843409f14e76abb`
- `spot/LINKUSDT_4h.csv`: `54826218f0534fd25036529b9354d24679b27321eaa8e4716dbaad177d602d6b`
- `spot/SOLUSDT_15m.csv`: `a63019d7ad1a2c8c497f37fc085ae04d1a7ad490bb28e671f50a266ceaa0818d`
- `spot/SOLUSDT_1d.csv`: `2408659f4e1a6420c6b53f448d3d379a84befdb70e8324b306bf4320e6ef71d8`
- `spot/SOLUSDT_1h.csv`: `e44b25d8c98f11265c8c59f9f83fe0577db4c5c719eef78e1fd9b157e7083c8e`
- `spot/SOLUSDT_4h.csv`: `c23089c65df013bf2f1d5ec2d91cb58af1aebe03f33af1ef9693f06de8baccb6`
- `spot/XRPUSDT_15m.csv`: `e423949129df88c24de6d43a92b64f4308de8d64e701dd1ade2e59721254153d`
- `spot/XRPUSDT_1d.csv`: `61c0e6747f56636396e5a632b6b3514907b9ed3ebca45fcfee370e31b783606c`
- `spot/XRPUSDT_1h.csv`: `7407f713942135f55546f082322db1e9b5a6124a6d44dbf4946fdd5090d579dd`
- `spot/XRPUSDT_4h.csv`: `91920e537adec956ae89811430839531106e297c90524b03d7ff571e4d805c10`

</details>

## Summary (OOS)

_No returns._

## By year

_n/a_

## By symbol

_Single series: no per-symbol breakdown available._

## By regime (ex-ante cell: trend_BTC x vol tercile)

_Regime labels not available._

## Coverage

| market | symbol | tf | status | first | last | bars | nan_bars | proxy |
|---|---|---|---|---|---|---|---|---|
| spot | BTCUSDT | 1d | ok | 2017-08-17 | 2026-10-14 | 3346 | 0 | no |
| spot | BTCUSDT | 4h | ok | 2017-08-17 | 2026-10-15 | 20077 | 17 | no |
| spot | BTCUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | BTCUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | ETHUSDT | 1d | ok | 2017-08-17 | 2026-10-14 | 3346 | 0 | no |
| spot | ETHUSDT | 4h | ok | 2017-08-17 | 2026-10-15 | 20077 | 17 | no |
| spot | ETHUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | ETHUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | BNBUSDT | 1d | ok | 2017-11-06 | 2026-10-14 | 3265 | 0 | no |
| spot | BNBUSDT | 4h | ok | 2017-11-06 | 2026-10-15 | 19592 | 16 | no |
| spot | BNBUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | BNBUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | SOLUSDT | 1d | ok | 2020-08-11 | 2026-10-14 | 2256 | 0 | no |
| spot | SOLUSDT | 4h | ok | 2020-08-11 | 2026-10-15 | 13537 | 0 | no |
| spot | SOLUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | SOLUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | XRPUSDT | 1d | ok | 2018-05-04 | 2026-10-14 | 3086 | 0 | no |
| spot | XRPUSDT | 4h | ok | 2018-05-04 | 2026-10-15 | 18516 | 9 | no |
| spot | XRPUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | XRPUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | ADAUSDT | 1d | ok | 2018-04-17 | 2026-10-14 | 3103 | 0 | no |
| spot | ADAUSDT | 4h | ok | 2018-04-17 | 2026-10-15 | 18619 | 9 | no |
| spot | ADAUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | ADAUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | DOGEUSDT | 1d | ok | 2019-07-05 | 2026-10-14 | 2659 | 0 | no |
| spot | DOGEUSDT | 4h | ok | 2019-07-05 | 2026-10-15 | 15953 | 2 | no |
| spot | DOGEUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | DOGEUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | AVAXUSDT | 1d | ok | 2020-09-22 | 2026-10-14 | 2214 | 0 | no |
| spot | AVAXUSDT | 4h | ok | 2020-09-22 | 2026-10-15 | 13285 | 0 | no |
| spot | AVAXUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | AVAXUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | LINKUSDT | 1d | ok | 2019-01-16 | 2026-10-14 | 2829 | 0 | no |
| spot | LINKUSDT | 4h | ok | 2019-01-16 | 2026-10-15 | 16974 | 5 | no |
| spot | LINKUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | LINKUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| spot | DOTUSDT | 1d | ok | 2020-08-18 | 2026-10-14 | 2249 | 0 | no |
| spot | DOTUSDT | 4h | ok | 2020-08-18 | 2026-10-15 | 13491 | 0 | no |
| spot | DOTUSDT | 1h | ok | 2022-01-01 | 2026-10-15 | 41960 | 2 | no |
| spot | DOTUSDT | 15m | ok | 2024-12-30 | 2026-10-15 | 62817 | 0 | no |
| futures | BTCUSDT | 1d | ok | 2020-09-01 | 2026-09-08 | 2199 | 0 | no |
| futures | BTCUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13199 | 0 | no |
| futures | BTCUSDT | 1h | ok | 2020-09-01 | 2026-09-09 | 52797 | 0 | no |
| futures | BTCUSDT | 15m | ok | 2020-09-01 | 2026-09-09 | 211189 | 6 | no |
| futures | ETHUSDT | 1d | ok | 2020-09-01 | 2026-09-08 | 2199 | 0 | no |
| futures | ETHUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13199 | 0 | no |
| futures | ETHUSDT | 1h | ok | 2020-09-01 | 2026-09-09 | 52798 | 0 | no |
| futures | ETHUSDT | 15m | ok | 2020-09-01 | 2026-09-09 | 211195 | 6 | no |
| futures | BNBUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | BNBUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13200 | 0 | no |
| futures | BNBUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52801 | 0 | no |
| futures | BNBUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211206 | 6 | no |
| futures | XRPUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | XRPUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13200 | 0 | no |
| futures | XRPUSDT | 1h | ok | 2020-09-01 | 2026-09-09 | 52800 | 0 | no |
| futures | XRPUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211201 | 6 | no |
| futures | DOGEUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | DOGEUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13200 | 0 | no |
| futures | DOGEUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52802 | 0 | no |
| futures | DOGEUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211208 | 6 | no |
| futures | ADAUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | ADAUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13200 | 0 | no |
| futures | ADAUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52802 | 0 | no |
| futures | ADAUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211211 | 6 | no |
| futures | LINKUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | LINKUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13200 | 0 | no |
| futures | LINKUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52803 | 0 | no |
| futures | LINKUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211214 | 6 | no |
| futures | DOTUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | DOTUSDT | 4h | ok | 2020-09-01 | 2026-09-10 | 13201 | 0 | no |
| futures | DOTUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52805 | 0 | no |
| futures | DOTUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211220 | 6 | no |
| futures | TRXUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | TRXUSDT | 4h | ok | 2020-09-01 | 2026-09-09 | 13200 | 0 | no |
| futures | TRXUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52803 | 0 | no |
| futures | TRXUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211213 | 6 | no |
| futures | LTCUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | LTCUSDT | 4h | ok | 2020-09-01 | 2026-09-10 | 13201 | 0 | no |
| futures | LTCUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52805 | 0 | no |
| futures | LTCUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211221 | 6 | no |
| futures | BCHUSDT | 1d | ok | 2020-09-01 | 2026-09-09 | 2200 | 0 | no |
| futures | BCHUSDT | 4h | ok | 2020-09-01 | 2026-09-10 | 13201 | 0 | no |
| futures | BCHUSDT | 1h | ok | 2020-09-01 | 2026-09-10 | 52806 | 0 | no |
| futures | BCHUSDT | 15m | ok | 2020-09-01 | 2026-09-10 | 211226 | 6 | no |
| futures | SOLUSDT | 1d | ok | 2020-09-15 | 2026-09-09 | 2186 | 0 | no |
| futures | SOLUSDT | 4h | ok | 2020-09-14 | 2026-09-09 | 13120 | 0 | no |
| futures | SOLUSDT | 1h | ok | 2020-09-14 | 2026-09-09 | 52481 | 0 | no |
| futures | SOLUSDT | 15m | ok | 2020-09-14 | 2026-09-10 | 209927 | 6 | no |
| futures | AVAXUSDT | 1d | ok | 2020-09-24 | 2026-09-09 | 2177 | 0 | no |
| futures | AVAXUSDT | 4h | ok | 2020-09-23 | 2026-09-10 | 13067 | 0 | no |
| futures | AVAXUSDT | 1h | ok | 2020-09-23 | 2026-09-10 | 52269 | 0 | no |
| futures | AVAXUSDT | 15m | ok | 2020-09-23 | 2026-09-10 | 209076 | 6 | no |
| futures | NEARUSDT | 1d | ok | 2020-10-16 | 2026-09-09 | 2155 | 0 | no |
| futures | NEARUSDT | 4h | ok | 2020-10-15 | 2026-09-10 | 12935 | 0 | no |
| futures | NEARUSDT | 1h | ok | 2020-10-15 | 2026-09-10 | 51740 | 0 | no |
| futures | NEARUSDT | 15m | ok | 2020-10-15 | 2026-09-10 | 206963 | 6 | no |
| futures | OPUSDT | 1d | ok | 2022-06-02 | 2026-09-09 | 1561 | 0 | no |
| futures | OPUSDT | 4h | ok | 2022-06-01 | 2026-09-10 | 9370 | 0 | no |
| futures | OPUSDT | 1h | ok | 2022-06-01 | 2026-09-10 | 37482 | 0 | no |
| futures | OPUSDT | 15m | ok | 2022-06-01 | 2026-09-10 | 149930 | 0 | no |
| futures | APTUSDT | 1d | ok | 2022-10-20 | 2026-09-09 | 1421 | 0 | no |
| futures | APTUSDT | 4h | ok | 2022-10-19 | 2026-09-10 | 8533 | 0 | no |
| futures | APTUSDT | 1h | ok | 2022-10-19 | 2026-09-10 | 34134 | 0 | no |
| futures | APTUSDT | 15m | ok | 2022-10-19 | 2026-09-10 | 136536 | 0 | no |
| futures | ARBUSDT | 1d | ok | 2023-03-24 | 2026-09-09 | 1266 | 0 | no |
| futures | ARBUSDT | 4h | ok | 2023-03-23 | 2026-09-10 | 7600 | 0 | no |
| futures | ARBUSDT | 1h | ok | 2023-03-23 | 2026-09-10 | 30401 | 0 | no |
| futures | ARBUSDT | 15m | ok | 2023-03-23 | 2026-09-10 | 121605 | 0 | no |
| futures | SUIUSDT | 1d | ok | 2023-05-04 | 2026-09-09 | 1225 | 0 | no |
| futures | SUIUSDT | 4h | ok | 2023-05-03 | 2026-09-10 | 7354 | 0 | no |
| futures | SUIUSDT | 1h | ok | 2023-05-03 | 2026-09-10 | 29416 | 0 | no |
| futures | SUIUSDT | 15m | ok | 2023-05-03 | 2026-09-10 | 117664 | 0 | no |

## Funding audit

| symbol | status | n | median_bps | mean_apr | share_zero | share_1e-4 | share_8h | other_intervals | annual_sums |
|---|---|---|---|---|---|---|---|---|---|
| BTCUSDT | ok | 6600 | 0.822 | 0.111 | 0.000 | 0.324 | 1.000 | 0 | 2020:0.053; 2021:0.306; 2022:0.042; 2023:0.079; 2024:0.120; 2025:0.051; 2026:0.019 |
| ETHUSDT | ok | 6600 | 0.827 | 0.123 | 0.000 | 0.312 | 1.000 | 0 | 2020:0.085; 2021:0.375; 2022:0.008; 2023:0.083; 2024:0.130; 2025:0.049; 2026:0.012 |
| BNBUSDT | ok | 6601 | 0.000 | -0.007 | 0.498 | 0.000 | 1.000 | 0 | 2020:-0.014; 2021:0.217; 2022:-0.126; 2023:-0.083; 2024:-0.033; 2025:-0.021; 2026:0.019 |
| XRPUSDT | ok | 6601 | 1.000 | 0.130 | 0.000 | 0.379 | 1.000 | 0 | 2020:0.044; 2021:0.481; 2022:0.000; 2023:0.082; 2024:0.142; 2025:0.035; 2026:-0.004 |
| DOGEUSDT | ok | 6601 | 1.000 | 0.124 | 0.000 | 0.407 | 1.000 | 0 | 2020:0.027; 2021:0.385; 2022:0.034; 2023:0.100; 2024:0.140; 2025:0.043; 2026:0.018 |
| ADAUSDT | ok | 6601 | 1.000 | 0.122 | 0.000 | 0.440 | 1.000 | 0 | 2020:0.088; 2021:0.399; 2022:-0.010; 2023:0.072; 2024:0.140; 2025:0.041; 2026:0.007 |
| LINKUSDT | ok | 6601 | 1.000 | 0.142 | 0.000 | 0.478 | 1.000 | 0 | 2020:0.050; 2021:0.430; 2022:0.059; 2023:0.102; 2024:0.134; 2025:0.051; 2026:0.032 |
| DOTUSDT | ok | 6601 | 0.861 | 0.073 | 0.000 | 0.360 | 1.000 | 0 | 2020:0.059; 2021:0.422; 2022:-0.143; 2023:0.016; 2024:0.115; 2025:0.011; 2026:-0.038 |
| TRXUSDT | ok | 6601 | 0.631 | 0.010 | 0.000 | 0.361 | 1.000 | 0 | 2020:0.008; 2021:0.281; 2022:-0.158; 2023:-0.036; 2024:0.034; 2025:-0.005; 2026:-0.063 |
| LTCUSDT | ok | 6601 | 1.000 | 0.136 | 0.000 | 0.400 | 1.000 | 0 | 2020:0.079; 2021:0.401; 2022:0.029; 2023:0.093; 2024:0.144; 2025:0.056; 2026:0.019 |
| BCHUSDT | ok | 6601 | 0.497 | 0.026 | 0.000 | 0.320 | 1.000 | 0 | 2020:0.031; 2021:0.337; 2022:-0.060; 2023:-0.090; 2024:-0.011; 2025:-0.026; 2026:-0.026 |
| SOLUSDT | ok | 6630 | 0.851 | 0.015 | 0.000 | 0.346 | 0.986 | 94 | 2020:-0.038; 2021:0.286; 2022:-0.300; 2023:0.013; 2024:0.137; 2025:0.004; 2026:-0.011 |
| AVAXUSDT | ok | 6534 | 1.000 | 0.069 | 0.000 | 0.390 | 1.000 | 0 | 2020:-0.035; 2021:0.310; 2022:-0.052; 2023:0.075; 2024:0.106; 2025:0.001; 2026:0.005 |
| NEARUSDT | ok | 6468 | 1.000 | 0.104 | 0.000 | 0.478 | 1.000 | 0 | 2020:0.026; 2021:0.377; 2022:-0.042; 2023:0.069; 2024:0.141; 2025:0.021; 2026:0.025 |
| OPUSDT | ok | 4686 | 1.000 | 0.069 | 0.000 | 0.408 | 1.000 | 0 | 2022:0.017; 2023:0.092; 2024:0.160; 2025:0.032; 2026:-0.003 |
| APTUSDT | ok | 4266 | 0.570 | -0.013 | 0.000 | 0.320 | 1.000 | 0 | 2022:-0.065; 2023:0.026; 2024:0.164; 2025:-0.127; 2026:-0.048 |
| ARBUSDT | ok | 3801 | 0.980 | 0.088 | 0.000 | 0.386 | 1.000 | 0 | 2023:0.085; 2024:0.160; 2025:0.049; 2026:0.012 |
| SUIUSDT | ok | 3677 | 0.641 | 0.055 | 0.000 | 0.301 | 1.000 | 0 | 2023:0.029; 2024:0.103; 2025:0.034; 2026:0.018 |

## Notes

- volume == 0 bars are masked as NaN by the loader (counted in nan_bars).
- BNBUSDT funding is excluded from every perp P&L (PLAN §5.2.2).
