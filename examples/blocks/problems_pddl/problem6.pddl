;; Problem 6: build a five‑block tower from scattered blocks
;; Initial state: blo_c80dc9, blo_0c8fa4, blo_5ce8c5, blo_ad722b and blo_3f7922 all sit individually on the table and are
;; clear.  The arm is empty.  Goal: stack the blocks to form the tower blo_3f7922 on blo_ad722b on
;; blo_5ce8c5 on blo_0c8fa4 on blo_c80dc9 (so blo_3f7922 is top and blo_c80dc9 is bottom).

(define (problem p06)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b blo_3f7922)
  (:init (arm-empty)
         (on-table blo_c80dc9) (on-table blo_0c8fa4) (on-table blo_5ce8c5) (on-table blo_ad722b) (on-table blo_3f7922)
         (clear blo_c80dc9) (clear blo_0c8fa4) (clear blo_5ce8c5) (clear blo_ad722b) (clear blo_3f7922))
  (:goal (and (on blo_3f7922 blo_ad722b) (on blo_ad722b blo_5ce8c5) (on blo_5ce8c5 blo_0c8fa4) (on blo_0c8fa4 blo_c80dc9)))
)