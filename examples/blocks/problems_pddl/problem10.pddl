;; Problem 10: merge two towers into a seven‑block tower
;; Initial state: there are seven blocks blo_c80dc9–blo_9d2bfe.  Blocks blo_c80dc9, blo_0c8fa4 and blo_5ce8c5 form a 3‑block
;; tower (blo_5ce8c5 on blo_0c8fa4 on blo_c80dc9 on the table).  Blocks blo_ad722b, blo_3f7922, blo_a0a2fa and blo_9d2bfe form a 4‑block tower
;; (blo_9d2bfe on blo_a0a2fa on blo_3f7922 on blo_ad722b on the table).  Blocks blo_5ce8c5 and blo_9d2bfe are clear and the arm is
;; empty.  Goal: create a single tower where blo_c80dc9 is on blo_0c8fa4, blo_0c8fa4 on blo_5ce8c5, blo_5ce8c5 on blo_ad722b, blo_ad722b on blo_3f7922,
;; blo_3f7922 on blo_a0a2fa and blo_a0a2fa on blo_9d2bfe (so blo_c80dc9 is top and blo_9d2bfe is bottom).  This demonstrates a more
;; complex seven‑block restructuring.

(define (problem p10)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b blo_3f7922 blo_a0a2fa blo_9d2bfe)
  (:init (arm-empty)
         ;; first tower (blo_5ce8c5 on blo_0c8fa4 on blo_c80dc9)
         (on blo_5ce8c5 blo_0c8fa4) (on blo_0c8fa4 blo_c80dc9) (on-table blo_c80dc9)
         ;; second tower (blo_9d2bfe on blo_a0a2fa on blo_3f7922 on blo_ad722b)
         (on blo_9d2bfe blo_a0a2fa) (on blo_a0a2fa blo_3f7922) (on blo_3f7922 blo_ad722b) (on-table blo_ad722b)
         ;; clear blocks
         (clear blo_5ce8c5) (clear blo_9d2bfe))
  (:goal (and (on blo_c80dc9 blo_0c8fa4) (on blo_0c8fa4 blo_5ce8c5) (on blo_5ce8c5 blo_ad722b) (on blo_ad722b blo_3f7922) (on blo_3f7922 blo_a0a2fa) (on blo_a0a2fa blo_9d2bfe)))
)