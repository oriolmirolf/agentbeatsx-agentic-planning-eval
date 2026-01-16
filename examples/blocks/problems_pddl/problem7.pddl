;; Problem 7: UNSOLVABLE (Spatial Contradiction)
;; Initial state: Tower B-A, Tower E-D.
;; Goal: blo_c80dc9 is on blo_0c8fa4 AND blo_c80dc9 is on blo_5ce8c5. Impossible.

(define (problem p07)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b blo_3f7922)
  (:init (arm-empty)
         (on blo_0c8fa4 blo_c80dc9) (on blo_5ce8c5 blo_0c8fa4) (on-table blo_c80dc9)
         (on blo_3f7922 blo_ad722b) (on-table blo_ad722b)
         (clear blo_5ce8c5) (clear blo_3f7922))
  ;; UNSOLVABLE MODIFICATION: blo_c80dc9 cannot be on blo_0c8fa4 and on blo_5ce8c5 at the same time.
  (:goal (and (on blo_c80dc9 blo_0c8fa4) (on blo_c80dc9 blo_5ce8c5) (on blo_5ce8c5 blo_ad722b) (on blo_ad722b blo_3f7922)))
)