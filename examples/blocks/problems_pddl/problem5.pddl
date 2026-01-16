;; Problem 5: UNSOLVABLE (Circular Goal)
;; Initial state: blo_ad722b is on blo_5ce8c5, blo_5ce8c5 on blo_0c8fa4, blo_0c8fa4 on blo_c80dc9 and blo_c80dc9 on the table.
;; Goal: blo_c80dc9 on blo_0c8fa4, blo_0c8fa4 on blo_5ce8c5, and blo_5ce8c5 on blo_c80dc9 (Circular dependency).

(define (problem p05)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b)
  (:init (arm-empty)
         (on-table blo_c80dc9)
         (on blo_0c8fa4 blo_c80dc9)
         (on blo_5ce8c5 blo_0c8fa4)
         (on blo_ad722b blo_5ce8c5)
         (clear blo_ad722b))
  ;; UNSOLVABLE MODIFICATION: Circular goal (A->B->C->blo_c80dc9)
  (:goal (and (on blo_c80dc9 blo_0c8fa4) (on blo_0c8fa4 blo_5ce8c5) (on blo_5ce8c5 blo_c80dc9)))
)