;; Problem 8 (five blocks): create a single tower from three separate stacks
;; Initial state: blo_0c8fa4 is on blo_c80dc9; blo_ad722b is on blo_5ce8c5; blo_3f7922 sits on the table alone.  Blocks blo_0c8fa4,
;; blo_ad722b and blo_3f7922 are clear and the arm is empty.  Goal: build a five‑block tower with
;; blo_5ce8c5 on blo_ad722b, blo_ad722b on blo_0c8fa4, blo_0c8fa4 on blo_c80dc9 and blo_c80dc9 on blo_3f7922 (from top to bottom: blo_5ce8c5, blo_ad722b, blo_0c8fa4, blo_c80dc9, blo_3f7922).
;; This task is the most difficult because it requires merging three stacks into a
;; single five‑block tower.

(define (problem p08)
  (:domain blocksworld)
  (:objects blo_c80dc9 blo_0c8fa4 blo_5ce8c5 blo_ad722b blo_3f7922)
  (:init (arm-empty)
         (on blo_0c8fa4 blo_c80dc9) (on-table blo_c80dc9)
         (on blo_ad722b blo_5ce8c5) (on-table blo_5ce8c5)
         (on-table blo_3f7922)
         (clear blo_0c8fa4) (clear blo_ad722b) (clear blo_3f7922))
  (:goal (and (on blo_5ce8c5 blo_ad722b) (on blo_ad722b blo_0c8fa4) (on blo_0c8fa4 blo_c80dc9) (on blo_c80dc9 blo_3f7922)))
)