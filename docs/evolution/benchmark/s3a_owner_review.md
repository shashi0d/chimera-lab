# S3a owner review (verbatim)

Collected Nov 1, 2026 from the side-by-side review sheet. Use as direction for general fixes, never as patches for these two images.

## Rhinoceros beetle x brown bear
Best: none. Worst: V4.

- V0: the beetle shell looks like it is kept on the body of bear, it doesnt feel like its an extension, the model is pasting the shell on bear, but should the idea be martch where what is coming, the idea is not to edit the image but edit the animal, does model disregard the bottom of the animal the hindlegs and stuff also the current implementation disregards scaling of the insect body on the bear,
- V1: 1. the scale extends to whole body but the first one doesnt liik like beetle, second one is good in terms of body, also if we said its armor for bear, the legs and other part should get it too, isnt it?
- V2: same problem as before
- V3: same as v2 v1
- V4: same as last 2
- V5: this is more worse, why did the hord come on node it looks like a cross of rhinoceros and bear than beetle
- Does any version look like the shell grew from the bear rather than sitting on it? Partly (v1 2nd image makes a little justice)
- Where should a back shield sit on a four-legged animal? No answer (the essence is exo skeleton forming, it need not retain shape perse, so if it formed on bear how would it to should be the direction)
- Does the horn look like part of the head? Yes (it looks like part of the head but with no connection to rest of the parts it looks out of place)

## Axolotl x Chinese pangolin
Best: V2. Worst: none.

- V1: i think the second image looks like this can potentially be an animal
- V2: same there are all good conceptual renderings
- V3: same as besidee
- V4: tail looks odd rest concept is hreat
- V5: yea other than tail being a little bigger i think this hybrid works, and v5 is a better implementation this is closer to a real hybrid now
- Can you see both animals clearly in the best version? No answer (yea one can tell what animals are)
- Do the scales look like the axolotl's own skin? Yes (the render is good it looks realisic and output makes sense)

## Synthesis (reviewer)

Root cause: the engine transfers parts (shapes) instead of traits that develop on the host body. Patterns: pasted donor shapes; partial coverage without a reason; donor-scale plates; disconnected parts from the same donor system; donor identity lost on discrete parts under edits. See S3b for the general fixes.
