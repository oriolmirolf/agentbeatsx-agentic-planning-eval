;; Problem 4: merge two towers into a single four‑block tower
;; Initial state: blo_c80dc9 sits on blo_0c8fa4; blo_ad722b sits on blo_5ce8c5.  Blocks blo_c80dc9 and blo_ad722b are clear.  blo_0c8fa4 and blo_5ce8c5
;; rest on the table.  The arm is empty.
;; Goal: build a tower with blo_c80dc9 on blo_0c8fa4, blo_0c8fa4 on blo_5ce8c5 and blo_5ce8c5 on blo_ad722b (so the final order from
;; top to bottom is blo_c80dc9, blo_0c8fa4, blo_5ce8c5, blo_ad722b).

(define (problem p04)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b)
  (:init (arm-empty)
         (on blo_c80dc9 blo_0c8fa4) (on-table blo_0c8fa4)
         (on blo_ad722b blo_5ce8c5) (on-table blo_5ce8c5)
         (clear blo_c80dc9) (clear blo_ad722b))
  (:goal (and (on blo_c80dc9 blo_0c8fa4) (on blo_0c8fa4 blo_5ce8c5) (on blo_5ce8c5 blo_ad722b)))
)