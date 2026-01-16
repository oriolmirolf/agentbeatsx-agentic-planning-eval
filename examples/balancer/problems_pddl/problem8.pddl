(define (problem loadbalance-p08)
  (:domain loadbalance)

  (:objects
    us_east eu_west - region
    search ads - service
    s1_us s2_us - server
    s3_eu s4_eu - server
    b1 b2 b3 b4 b5 b6 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_us us_east)
    (server-region s2_us us_east)
    (server-region s3_eu eu_west)
    (server-region s4_eu eu_west)

    (bucket-region b1 us_east)
    (bucket-region b2 us_east)
    (bucket-region b3 us_east)
    (bucket-region b4 eu_west)
    (bucket-region b5 eu_west)
    (bucket-region b6 eu_west)

    (bucket-service b1 search)
    (bucket-service b2 search)
    (bucket-service b3 ads)
    (bucket-service b4 search)
    (bucket-service b5 search)
    (bucket-service b6 ads)

    (online s1_us)
    (online s2_us)
    (online s3_eu)
    (not (online s4_eu))

    ;; us-east: s1_us search only; s2_us search+ads
    (runs s1_us search)
    (runs s2_us search)
    (runs s2_us ads)

    ;; eu-west: s3_eu search only initially
    (runs s3_eu search)

    ;; assignments
    (assigned-to b1 s1_us)
    (assigned-to b2 s2_us)
    (assigned-to b3 s2_us)
    (assigned-to b4 s1_us) ; wrong region
    (unassigned b5)
    (unassigned b6)

    (= (capacity s1_us) 3)
    (= (capacity s2_us) 3)
    
    ;; UNSOLVABLE MODIFICATION: Capacity reduced from 3 to 2
    ;; Goal requires assigning b4, b5, b6 (3 items) to s3_eu.
    (= (capacity s3_eu) 2)
    (= (capacity s4_eu) 3)

    (= (load s1_us) 2) ; b1, b4
    (= (load s2_us) 2) ; b2, b3
    (= (load s3_eu) 0)
    (= (load s4_eu) 0)
  )

  (:goal
    (and
      (assigned-to b1 s2_us)
      (assigned-to b2 s2_us)
      (assigned-to b3 s2_us)
      (assigned-to b4 s3_eu)
      (assigned-to b5 s3_eu)
      (assigned-to b6 s3_eu)
      (online s2_us)
      (online s3_eu)
      (not (online s1_us))
    )
  )

  (:metric minimize (total-cost))
)