;; Problem 9: build a six‑block tower from scratch
;; Initial state: six blocks blo_c80dc9–blo_a0a2fa are all on the table and clear.  The arm is
;; empty.  Goal: assemble them into a single tower with blo_a0a2fa on blo_3f7922, blo_3f7922 on blo_ad722b, blo_ad722b on blo_5ce8c5,
;; blo_5ce8c5 on blo_0c8fa4 and blo_0c8fa4 on blo_c80dc9 (so blo_a0a2fa is top and blo_c80dc9 is bottom).  This problem shows how
;; Blocksworld can scale beyond five blocks.

(define (problem p09)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b blo_3f7922 blo_a0a2fa)
  (:init (arm-empty)
         (on-table blo_c80dc9) (on-table blo_0c8fa4) (on-table blo_5ce8c5) (on-table blo_ad722b) (on-table blo_3f7922) (on-table blo_a0a2fa)
         (clear blo_c80dc9) (clear blo_0c8fa4) (clear blo_5ce8c5) (clear blo_ad722b) (clear blo_3f7922) (clear blo_a0a2fa))
  (:goal (and (on blo_a0a2fa blo_3f7922) (on blo_3f7922 blo_ad722b) (on blo_ad722b blo_5ce8c5) (on blo_5ce8c5 blo_0c8fa4) (on blo_0c8fa4 blo_c80dc9)))
)