;; Problem 3: reverse a three‑block tower (example from the UMBC lecture notes)
;; Initial state: blo_5ce8c5 is on blo_0c8fa4, which is on blo_c80dc9, which is on the table.  Block blo_5ce8c5 is
;; clear and the arm is empty.  Goal: have blo_c80dc9 on blo_0c8fa4 and blo_0c8fa4 on blo_5ce8c5【789902751098195†L211-L227】.

(define (problem p03)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5)
  (:init (arm-empty)
         (on-table blo_c80dc9)
         (on blo_0c8fa4 blo_c80dc9)
         (on blo_5ce8c5 blo_0c8fa4)
         (clear blo_5ce8c5))
  (:goal (and (on blo_c80dc9 blo_0c8fa4) (on blo_0c8fa4 blo_5ce8c5)))
)