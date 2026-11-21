import type { Branch } from '../domain/types'

// Static academic catalog fallback used when API is unreachable or during cold starts
export const FALLBACK_BRANCHES: Branch[] = [
  {
    "branch_id": 1,
    "branch_key": "btech",
    "name": "B.Tech",
    "degree_level": "undergraduate",
    "sort_order": 0,
    "programs": [
      {
        "program_id": 1,
        "program_key": "btech_civil",
        "name": "Civil Engineering",
        "full_name": "B.Tech - Civil Engineering",
        "collaboration_partner": null,
        "sort_order": 0
      },
      {
        "program_id": 2,
        "program_key": "btech_mechanical",
        "name": "Mechanical Engineering",
        "full_name": "B.Tech - Mechanical Engineering",
        "collaboration_partner": null,
        "sort_order": 1
      },
      {
        "program_id": 3,
        "program_key": "btech_aerospace",
        "name": "Aerospace Engineering",
        "full_name": "B.Tech - Aerospace Engineering",
        "collaboration_partner": null,
        "sort_order": 2
      },
      {
        "program_id": 4,
        "program_key": "btech_ece",
        "name": "Electronics and Communication Engineering",
        "full_name": "B.Tech - Electronics and Communication Engineering",
        "collaboration_partner": null,
        "sort_order": 3
      },
      {
        "program_id": 5,
        "program_key": "btech_biotech",
        "name": "Biotechnology",
        "full_name": "B.Tech - Biotechnology",
        "collaboration_partner": null,
        "sort_order": 4
      },
      {
        "program_id": 6,
        "program_key": "btech_electrical",
        "name": "Electrical Engineering",
        "full_name": "B.Tech - Electrical Engineering",
        "collaboration_partner": null,
        "sort_order": 5
      },
      {
        "program_id": 7,
        "program_key": "btech_robotics",
        "name": "Robotics & Automation",
        "full_name": "B.Tech - Robotics & Automation",
        "collaboration_partner": null,
        "sort_order": 6
      },
      {
        "program_id": 8,
        "program_key": "btech_cse_aiml",
        "name": "CSE with AI & ML",
        "full_name": "B.Tech - CSE with AI & ML",
        "collaboration_partner": "Microsoft",
        "sort_order": 7
      },
      {
        "program_id": 9,
        "program_key": "btech_cse_ds",
        "name": "CSE with Data Science",
        "full_name": "B.Tech - CSE with Data Science",
        "collaboration_partner": "Google",
        "sort_order": 8
      },
      {
        "program_id": 10,
        "program_key": "btech_cybersecurity",
        "name": "CSE Cyber Security",
        "full_name": "B.Tech - CSE Cyber Security",
        "collaboration_partner": "Quick Heal",
        "sort_order": 9
      },
      {
        "program_id": 11,
        "program_key": "btech_cloud",
        "name": "CSE with Cloud Computing",
        "full_name": "B.Tech - CSE with Cloud Computing",
        "collaboration_partner": "Google",
        "sort_order": 10
      },
      {
        "program_id": 12,
        "program_key": "btech_cse",
        "name": "Computer Science & Engineering",
        "full_name": "B.Tech - Computer Science & Engineering",
        "collaboration_partner": null,
        "sort_order": 11
      },
      {
        "program_id": 13,
        "program_key": "btech_it",
        "name": "Information Technology",
        "full_name": "B.Tech - Information Technology",
        "collaboration_partner": null,
        "sort_order": 12
      },
      {
        "program_id": 14,
        "program_key": "btech_iot_ai",
        "name": "CSE IoT & AI",
        "full_name": "B.Tech - CSE IoT & AI",
        "collaboration_partner": null,
        "sort_order": 13
      }
    ]
  },
  {
    "branch_id": 2,
    "branch_key": "mtech",
    "name": "M.Tech",
    "degree_level": "postgraduate",
    "sort_order": 1,
    "programs": [
      {
        "program_id": 15,
        "program_key": "mtech_cse_aiml",
        "name": "CSE with AI & ML",
        "full_name": "M.Tech - CSE with AI & ML",
        "collaboration_partner": "SAS",
        "sort_order": 14
      },
      {
        "program_id": 16,
        "program_key": "mtech_cse_ds",
        "name": "CSE Data Science",
        "full_name": "M.Tech - CSE Data Science",
        "collaboration_partner": null,
        "sort_order": 15
      }
    ]
  },
  {
    "branch_id": 3,
    "branch_key": "bsc",
    "name": "B.Sc.",
    "degree_level": "undergraduate",
    "sort_order": 2,
    "programs": [
      {
        "program_id": 17,
        "program_key": "bsc_ds",
        "name": "Data Science",
        "full_name": "B.Sc. (Hons./Hons. with Research) Data Science",
        "collaboration_partner": null,
        "sort_order": 16
      },
      {
        "program_id": 18,
        "program_key": "bsc_biotech",
        "name": "Biotechnology",
        "full_name": "B.Sc. (Hons./Hons. with Research) Biotechnology",
        "collaboration_partner": null,
        "sort_order": 17
      },
      {
        "program_id": 19,
        "program_key": "bsc_forensic",
        "name": "Forensic Science",
        "full_name": "B.Sc. (Hons./Hons. with Research) Forensic Science",
        "collaboration_partner": null,
        "sort_order": 18
      },
      {
        "program_id": 20,
        "program_key": "bsc_microbiology",
        "name": "Microbiology",
        "full_name": "B.Sc. (Hons./Hons. with Research) Microbiology",
        "collaboration_partner": null,
        "sort_order": 19
      },
      {
        "program_id": 52,
        "program_key": "bsc_animation",
        "name": "Animation, VFX & Gaming",
        "full_name": "B.Sc. (Hons) - Animation, VFX & Gaming",
        "collaboration_partner": null,
        "sort_order": 51
      }
    ]
  },
  {
    "branch_id": 4,
    "branch_key": "msc",
    "name": "M.Sc.",
    "degree_level": "postgraduate",
    "sort_order": 3,
    "programs": [
      {
        "program_id": 21,
        "program_key": "msc_ds",
        "name": "Data Science",
        "full_name": "M.Sc. Data Science",
        "collaboration_partner": null,
        "sort_order": 20
      },
      {
        "program_id": 22,
        "program_key": "msc_biotech",
        "name": "Biotechnology",
        "full_name": "M.Sc. Biotechnology",
        "collaboration_partner": null,
        "sort_order": 21
      }
    ]
  },
  {
    "branch_id": 5,
    "branch_key": "bba",
    "name": "BBA",
    "degree_level": "undergraduate",
    "sort_order": 4,
    "programs": [
      {
        "program_id": 23,
        "program_key": "bba_hons",
        "name": "Business Administration (Hons)",
        "full_name": "BBA (Hons)",
        "collaboration_partner": null,
        "sort_order": 22
      },
      {
        "program_id": 24,
        "program_key": "bba_branding",
        "name": "Branding & Advertising (Hons)",
        "full_name": "BBA - Branding & Advertising (Hons)",
        "collaboration_partner": null,
        "sort_order": 23
      },
      {
        "program_id": 25,
        "program_key": "bba_fintech_acca",
        "name": "Fintech + ACCA (International Accounting & Finance)",
        "full_name": "BBA Fintech + ACCA (International Accounting & Finance)",
        "collaboration_partner": "Grant Thornton; ACCA",
        "sort_order": 24
      },
      {
        "program_id": 26,
        "program_key": "bba_business_analytics",
        "name": "Business Analytics (Hons)",
        "full_name": "BBA(H) - Business Analytics",
        "collaboration_partner": "Deloitte",
        "sort_order": 25
      }
    ]
  },
  {
    "branch_id": 6,
    "branch_key": "bba_dm",
    "name": "BBA-DM",
    "degree_level": "undergraduate",
    "sort_order": 5,
    "programs": [
      {
        "program_id": 27,
        "program_key": "bba_dm_hons",
        "name": "BBA-DM (Hons)",
        "full_name": "BBA-DM (Hons)",
        "collaboration_partner": null,
        "sort_order": 26
      }
    ]
  },
  {
    "branch_id": 7,
    "branch_key": "mba",
    "name": "MBA",
    "degree_level": "postgraduate",
    "sort_order": 6,
    "programs": [
      {
        "program_id": 28,
        "program_key": "mba_applied_finance",
        "name": "Applied Finance",
        "full_name": "MBA - Applied Finance",
        "collaboration_partner": "PwC",
        "sort_order": 27
      },
      {
        "program_id": 29,
        "program_key": "mba_fintech",
        "name": "Fintech",
        "full_name": "MBA Fintech",
        "collaboration_partner": "NAL Academy",
        "sort_order": 28
      },
      {
        "program_id": 30,
        "program_key": "mba_ds_ai",
        "name": "Data Science & AI",
        "full_name": "MBA - Data Science & AI",
        "collaboration_partner": "SAS",
        "sort_order": 29
      },
      {
        "program_id": 31,
        "program_key": "mba_business_analytics",
        "name": "Business Analytics",
        "full_name": "MBA Business Analytics",
        "collaboration_partner": "IBM",
        "sort_order": 30
      },
      {
        "program_id": 32,
        "program_key": "mba_strategic_hr",
        "name": "Strategic HR",
        "full_name": "MBA - Strategic HR",
        "collaboration_partner": "AON",
        "sort_order": 31
      },
      {
        "program_id": 33,
        "program_key": "mba_global_business",
        "name": "Global Business Management",
        "full_name": "MBA - Global Business Management",
        "collaboration_partner": "Grant Thornton",
        "sort_order": 32
      },
      {
        "program_id": 34,
        "program_key": "mba_digital_marketing",
        "name": "Digital Marketing",
        "full_name": "MBA (Digital Marketing)",
        "collaboration_partner": null,
        "sort_order": 33
      }
    ]
  },
  {
    "branch_id": 8,
    "branch_key": "ba",
    "name": "B.A.",
    "degree_level": "undergraduate",
    "sort_order": 7,
    "programs": [
      {
        "program_id": 35,
        "program_key": "ba_liberal_arts",
        "name": "Liberal Arts (Hons)",
        "full_name": "B.A. Liberal Arts (Hons)",
        "collaboration_partner": null,
        "sort_order": 34
      },
      {
        "program_id": 36,
        "program_key": "ba_psychology",
        "name": "Psychology (Hons.)",
        "full_name": "B.A. Psychology (Hons.)",
        "collaboration_partner": null,
        "sort_order": 35
      }
    ]
  },
  {
    "branch_id": 9,
    "branch_key": "llb",
    "name": "LLB",
    "degree_level": "undergraduate",
    "sort_order": 8,
    "programs": [
      {
        "program_id": 37,
        "program_key": "llb_general",
        "name": "Bachelor of Law (LLB)",
        "full_name": "Bachelor of Law (LLB)",
        "collaboration_partner": null,
        "sort_order": 36
      }
    ]
  },
  {
    "branch_id": 10,
    "branch_key": "ballb",
    "name": "B.A.LL.B.",
    "degree_level": "integrated",
    "sort_order": 9,
    "programs": [
      {
        "program_id": 38,
        "program_key": "ballb_integrated",
        "name": "B.A.LL.B. (Hons) Integrated",
        "full_name": "B.A.LL.B. (Hons) Integrated",
        "collaboration_partner": null,
        "sort_order": 37
      }
    ]
  },
  {
    "branch_id": 11,
    "branch_key": "bbal_lb",
    "name": "BBA.LL.B.",
    "degree_level": "integrated",
    "sort_order": 10,
    "programs": [
      {
        "program_id": 39,
        "program_key": "bbal_lb_integrated",
        "name": "BBA.LL.B. (Hons) Integrated",
        "full_name": "BBA.LL.B. (Hons) Integrated",
        "collaboration_partner": null,
        "sort_order": 38
      }
    ]
  },
  {
    "branch_id": 12,
    "branch_key": "llm",
    "name": "LL.M.",
    "degree_level": "postgraduate",
    "sort_order": 11,
    "programs": [
      {
        "program_id": 40,
        "program_key": "llm_criminal",
        "name": "Criminal Law",
        "full_name": "LL.M. in Criminal Law",
        "collaboration_partner": null,
        "sort_order": 39
      },
      {
        "program_id": 41,
        "program_key": "llm_constitutional",
        "name": "Constitutional Law",
        "full_name": "LL.M. in Constitutional Law",
        "collaboration_partner": null,
        "sort_order": 40
      },
      {
        "program_id": 42,
        "program_key": "llm_corporate",
        "name": "Corporate and Business Law",
        "full_name": "LL.M. in Corporate and Business Law",
        "collaboration_partner": null,
        "sort_order": 41
      }
    ]
  },
  {
    "branch_id": 13,
    "branch_key": "bca",
    "name": "BCA",
    "degree_level": "undergraduate",
    "sort_order": 12,
    "programs": [
      {
        "program_id": 43,
        "program_key": "bca_hons",
        "name": "BCA (Hons)",
        "full_name": "BCA (Hons)",
        "collaboration_partner": null,
        "sort_order": 42
      },
      {
        "program_id": 44,
        "program_key": "bca_aiml",
        "name": "BCA (Hons) AI & ML",
        "full_name": "BCA (Hons) AI & ML",
        "collaboration_partner": null,
        "sort_order": 43
      },
      {
        "program_id": 45,
        "program_key": "bca_ds",
        "name": "Data Science",
        "full_name": "BCA(H) - Data Science",
        "collaboration_partner": "SAS",
        "sort_order": 44
      }
    ]
  },
  {
    "branch_id": 14,
    "branch_key": "mca",
    "name": "MCA",
    "degree_level": "postgraduate",
    "sort_order": 13,
    "programs": [
      {
        "program_id": 46,
        "program_key": "mca_general",
        "name": "MCA",
        "full_name": "MCA",
        "collaboration_partner": null,
        "sort_order": 45
      },
      {
        "program_id": 47,
        "program_key": "mca_ds",
        "name": "Data Science",
        "full_name": "MCA Data Science",
        "collaboration_partner": null,
        "sort_order": 46
      },
      {
        "program_id": 48,
        "program_key": "mca_aiml",
        "name": "AI & ML",
        "full_name": "MCA - AI & ML",
        "collaboration_partner": "SAS",
        "sort_order": 47
      }
    ]
  },
  {
    "branch_id": 15,
    "branch_key": "bdes",
    "name": "Bachelor of Design (B.Des)",
    "degree_level": "undergraduate",
    "sort_order": 14,
    "programs": [
      {
        "program_id": 49,
        "program_key": "bdes_fashion",
        "name": "Fashion & Design",
        "full_name": "Bachelor of Design - Fashion & Design",
        "collaboration_partner": null,
        "sort_order": 48
      },
      {
        "program_id": 50,
        "program_key": "bdes_interior",
        "name": "Interior Design",
        "full_name": "Bachelor of Design - Interior Design",
        "collaboration_partner": null,
        "sort_order": 49
      }
    ]
  },
  {
    "branch_id": 16,
    "branch_key": "bajmc",
    "name": "B.A.-JMC",
    "degree_level": "undergraduate",
    "sort_order": 15,
    "programs": [
      {
        "program_id": 51,
        "program_key": "bajmc_general",
        "name": "Journalism and Mass Communication",
        "full_name": "BA-JMC",
        "collaboration_partner": null,
        "sort_order": 50
      }
    ]
  },
  {
    "branch_id": 17,
    "branch_key": "bcom",
    "name": "B.Com",
    "degree_level": "undergraduate",
    "sort_order": 16,
    "programs": [
      {
        "program_id": 53,
        "program_key": "bcom_hons",
        "name": "Commerce (Hons)",
        "full_name": "B. Com (Hons)",
        "collaboration_partner": null,
        "sort_order": 52
      },
      {
        "program_id": 54,
        "program_key": "bcom_acca",
        "name": "Commerce (Hons) + ACCA (International Accounting & Finance)",
        "full_name": "B.Com(H) + ACCA (International Accounting & Finance)",
        "collaboration_partner": "Grant Thornton; ACCA",
        "sort_order": 53
      }
    ]
  },
  {
    "branch_id": 18,
    "branch_key": "bpharm",
    "name": "Bachelor of Pharmacy",
    "degree_level": "undergraduate",
    "sort_order": 17,
    "programs": [
      {
        "program_id": 55,
        "program_key": "bpharm_general",
        "name": "Bachelor of Pharmacy",
        "full_name": "Bachelor of Pharmacy",
        "collaboration_partner": null,
        "sort_order": 54
      }
    ]
  },
  {
    "branch_id": 19,
    "branch_key": "hospitality",
    "name": "B.Sc. Hotel and Hospitality Management",
    "degree_level": "undergraduate",
    "sort_order": 18,
    "programs": [
      {
        "program_id": 56,
        "program_key": "hospitality_general",
        "name": "Hotel and Hospitality Management",
        "full_name": "B.Sc. - Hotel and Hospitality Management",
        "collaboration_partner": null,
        "sort_order": 55
      }
    ]
  },
  {
    "branch_id": 20,
    "branch_key": "airlines_airport",
    "name": "B.Sc. Airlines & Airport Management",
    "degree_level": "undergraduate",
    "sort_order": 19,
    "programs": [
      {
        "program_id": 57,
        "program_key": "airlines_airport_general",
        "name": "Airlines & Airport Management",
        "full_name": "B.Sc. - Airlines & Airport Management",
        "collaboration_partner": null,
        "sort_order": 56
      }
    ]
  },
  {
    "branch_id": 21,
    "branch_key": "barch",
    "name": "B.Arch",
    "degree_level": "undergraduate",
    "sort_order": 20,
    "programs": [
      {
        "program_id": 58,
        "program_key": "barch_general",
        "name": "Architecture",
        "full_name": "B.Arch",
        "collaboration_partner": null,
        "sort_order": 57
      }
    ]
  },
  {
    "branch_id": 22,
    "branch_key": "phd",
    "name": "Ph.D.",
    "degree_level": "doctoral",
    "sort_order": 21,
    "programs": [
      {
        "program_id": 59,
        "program_key": "phd_admissions",
        "name": "Ph.D. Admissions",
        "full_name": "Ph.D. Admissions",
        "collaboration_partner": null,
        "sort_order": 58
      }
    ]
  }
]
