;; Problem 1: build a three‑block tower from three blocks on the table
;; Initial state: blo_c80dc9, blo_0c8fa4 and blo_5ce8c5 are each on the table and clear with an empty arm
;; Goal: stack blo_c80dc9 on blo_0c8fa4 and blo_0c8fa4 on blo_5ce8c5【789902751098195†L118-L198】.

(define (problem p01)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5)
  (:init (arm-empty)
         (on-table blo_c80dc9) (on-table blo_0c8fa4) (on-table blo_5ce8c5)
         (clear blo_c80dc9) (clear blo_0c8fa4) (clear blo_5ce8c5))
  (:goal (and (on blo_c80dc9 blo_0c8fa4) (on blo_0c8fa4 blo_5ce8c5)))
)