(define (problem gripper-p04)
  (:domain gripper)
  (:objects
    roo_bcabae roo_59c817 - room
    gri_32fce4 gri_42e92a - gripper
    bal_07e7cd bal_e201c6 bal_58c0e0 bal_a03846 - ball
  )
  (:init
    (= (total-cost) 0)
    (at-robot roo_bcabae)
    (free gri_32fce4)
    (free gri_42e92a)
    (at bal_07e7cd roo_bcabae)
(at bal_e201c6 roo_bcabae)
(at bal_58c0e0 roo_bcabae)
(at bal_a03846 roo_bcabae)
  )
  (:goal (and
    (at bal_07e7cd roo_59c817)
    (at bal_e201c6 roo_59c817)
    (at bal_58c0e0 roo_59c817)
    (at bal_a03846 roo_59c817)
  ))
  (:metric minimize (total-cost))
)
