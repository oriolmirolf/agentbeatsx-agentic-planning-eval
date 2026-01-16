(define (problem loadbalance-p09)
  (:domain loadbalance)

  (:objects
    us_east ap_south - region
    payments search analytics - service
    s1_us s2_us - server
    s3_ap s4_ap - server
    b1 b2 b3 b4 b5 b6 b7 - bucket
  )

  (:init
    (= (total-cost) 0)
    (server-region s1_us us_east)
    (server-region s2_us us_east)
    (server-region s3_ap ap_south)
    (server-region s4_ap ap_south)

    (bucket-region b1 us_east)
    (bucket-region b2 us_east)
    (bucket-region b3 us_east)
    (bucket-region b4 us_east)
    (bucket-region b5 us_east)
    (bucket-region b6 ap_south)
    (bucket-region b7 ap_south)

    (bucket-service b1 payments)
    (bucket-service b2 payments)
    (bucket-service b3 analytics)
    (bucket-service b4 search)
    (bucket-service b5 search)
    (bucket-service b6 search)
    (bucket-service b7 payments)

    (online s1_us)
    (online s2_us)
    (online s3_ap)
    (not (online s4_ap))

    ;; s1_us: payments + search
    (runs s1_us payments)
    (runs s1_us search)

    ;; s2_us: analytics
    (runs s2_us analytics)

    ;; s3_ap: search only
    (runs s3_ap search)

    ;; initial assignments
    (assigned-to b1 s1_us)
    (assigned-to b4 s1_us)
    (assigned-to b2 s2_us)
    (assigned-to b3 s2_us)  ;; s2_us is full
    (assigned-to b5 s3_ap)  ;; wrong region (us_east bucket in ap_south)
    (unassigned b6)
    (assigned-to b7 s1_us)  ;; wrong region (ap_south bucket in us_east)

    (= (capacity s1_us) 4)
    (= (capacity s2_us) 2)
    (= (capacity s3_ap) 3)
    (= (capacity s4_ap) 3)

    (= (load s1_us) 3) ; b1,b4,b7
    (= (load s2_us) 2) ; b2,b3
    (= (load s3_ap) 1) ; b5
    (= (load s4_ap) 0)
  )

  ;; Canonical goal (one possible good configuration):
  ;; - US-EAST: b1,b2,b4,b5 on s1_us; b3 (analytics) on s2_us
  ;; - AP-SOUTH: b6,b7 on s3_ap
  (:goal
    (and
      (assigned-to b1 s1_us)
      (assigned-to b2 s1_us)
      (assigned-to b4 s1_us)
      (assigned-to b5 s1_us)
      (assigned-to b3 s2_us)
      (assigned-to b6 s3_ap)
      (assigned-to b7 s3_ap)
    )
  )

  (:metric minimize (total-cost))
)