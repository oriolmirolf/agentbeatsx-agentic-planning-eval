;; Problem 2: re‑arrange blocks from a simple stack to a different tower
;; Initial state: blo_0c8fa4 sits on blo_c80dc9 and blo_5ce8c5 sits directly on the table.  Blocks blo_0c8fa4 and blo_5ce8c5
;; are clear, while blo_c80dc9 is not.  The robot arm is empty.
;; Goal: build a new tower with blo_c80dc9 on blo_5ce8c5 and blo_0c8fa4 on blo_c80dc9.

(define (problem p02)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5)
  (:init (arm-empty)
         (on blo_0c8fa4 blo_c80dc9) (on-table blo_c80dc9)
         (on-table blo_5ce8c5)
         (clear blo_0c8fa4) (clear blo_5ce8c5))
  (:goal (and (on blo_c80dc9 blo_5ce8c5) (on blo_0c8fa4 blo_c80dc9)))
)