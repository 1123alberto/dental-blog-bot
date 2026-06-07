import unittest
from unittest.mock import MagicMock, patch
import generator
import scraper

class TestDentalBlogPipeline(unittest.TestCase):

    def setUp(self):
        self.sample_articles = [
            {
                "title": "Innovative Dental Implants Show High Osseointegration Rates",
                "source": "Journal of Clinical Periodontology",
                "summary": "A new study on dental implants shows excellent osseointegration over 5 years.",
                "full_text": "A new study on dental implants shows excellent osseointegration over 5 years of tracking patients. The results suggest high predictability.",
                "image": "https://wiley.com/assets/clinical-implant.jpg",
                "date": "May 15, 2026"
            },
            {
                "title": "Dental Implants and Osseointegration: A New Study",
                "source": "Dental Tribune",
                "summary": "Study shows high osseointegration rates for new implant designs.",
                "full_text": "Study shows high osseointegration rates.",
                "image": None,
                "date": "May 14, 2026"
            },
            {
                "title": "Preventive Brushing Methods for Children's Oral Health",
                "source": "ADA New Dentist Blog",
                "summary": "Tips on helping kids learn proper tooth brushing techniques.",
                "full_text": "Preventive brushing is key for pediatric oral health. Tips on helping kids learn proper brushing techniques include timer apps and parental tracking.",
                "image": "https://newdentistblog.ada.org/kids-brushing-stock.jpg",
                "date": "May 16, 2026"
            },
            {
                "title": "Dentistry Today corporate acquisition of dental software company",
                "source": "Dental Business News",
                "summary": "Dental Tech Corp acquires Software Solutions for 10 million dollars.",
                "full_text": "Dental Tech Corp acquires Software Solutions for 10 million dollars in cash and stocks. The quarterly earnings report is pending.",
                "image": "https://business.com/logo-avatar.png",
                "date": "May 17, 2026"
            }
        ]

    def test_deduplication_engine(self):
        # The first two articles in setUp are duplicates (Jaccard title similarity > 0.35)
        # Article 1 is from Tier 1 (Journal of Clinical Periodontology) and has an image.
        # Article 2 is from Tier 2 (Dental Tribune) and has no image.
        # Deduplication should group them and keep Article 1.
        deduplicated = generator.deduplicate_articles(self.sample_articles)
        
        # Verify deduplicated count is 3 (Article 1, Article 3, Article 4)
        self.assertEqual(len(deduplicated), 3)
        
        # Check that Article 1 remains and Article 2 is removed
        titles = [a["title"] for a in deduplicated]
        self.assertIn("Innovative Dental Implants Show High Osseointegration Rates", titles)
        self.assertNotIn("Dental Implants and Osseointegration: A New Study", titles)

    def test_heuristic_scoring_and_classification(self):
        # When Gemini client is not present, it should fallback to heuristic scoring
        processed = generator.score_and_classify_articles(None, self.sample_articles.copy())
        
        # Article 1 should be categorized under Implantology due to title keywords
        self.assertEqual(processed[0]["category"], "Implantology")
        self.assertEqual(processed[0]["scores"]["clinical_relevance"], 8) # Tier 1 default score
        
        # Article 3 should be categorized under Preventive dentistry
        self.assertEqual(processed[2]["category"], "Preventive dentistry")
        
        # Article 4 should be recognized as promotional due to business/corporate terms
        self.assertTrue(processed[3]["is_promotional"])

    def test_image_scorer(self):
        # Test clinical/authentic image (Wiley / Journal)
        score1 = generator.score_image(self.sample_articles[0])
        self.assertEqual(score1, 10)
        
        # Test generic stock image
        score3 = generator.score_image(self.sample_articles[2])
        self.assertEqual(score3, 5)
        
        # Test blacklisted avatar image
        score4 = generator.score_image(self.sample_articles[3])
        self.assertEqual(score4, 0)
        
        # Test missing image
        self.assertEqual(generator.score_image({"image": None}), 0)

    def test_history_filter(self):
        recent_posts = [
            "Innovative Dental Implants osseointegration report",
            "Random unrelated news about wisdom teeth"
        ]
        
        articles = self.sample_articles.copy()
        # Mock scores first
        for a in articles:
            a["scores"] = {"clinical_relevance": 5}
            
        filtered = generator.apply_history_filter(articles, recent_posts)
        
        # Article 1 has high title similarity (Jaccard > 0.35) to the first recent post
        # Thus, it should receive a penalty of 40
        self.assertEqual(filtered[0]["history_penalty"], 40)
        
        # Article 3 is unrelated, should have 0 penalty
        self.assertEqual(filtered[2]["history_penalty"], 0)

    def test_top_3_candidates(self):
        articles = self.sample_articles.copy()
        
        # Mock scores and classification
        for a in articles:
            a["scores"] = {
                "clinical_relevance": 10,
                "scientific_credibility": 10,
                "educational_value": 10,
                "innovation_significance": 10,
                "public_interest": 10,
                "practical_patient_relevance": 10
            }
            a["category"] = "MockCategory"
            a["is_promotional"] = False
            a["is_low_quality"] = False
            a["history_penalty"] = 0
            
        # Give Article 4 promotional penalty
        articles[3]["is_promotional"] = True
        
        top_3 = generator.get_top_3_candidates(articles)
        
        self.assertEqual(len(top_3), 3)
        # Check that Article 1 (implant) is in the top 3 with a high score (60 + 10 = 70)
        self.assertEqual(top_3[0]["title"], "Innovative Dental Implants Show High Osseointegration Rates")
        self.assertEqual(top_3[0]["final_score"], 70) # 60 positive + 10 image score
        
        # Article 4 (promotional) should be sorted to the bottom or excluded from top candidates
        titles = [a["title"] for a in top_3]
        self.assertNotIn("Dentistry Today corporate acquisition of dental software company", titles)

    @patch('google.genai.Client')
    def test_pipeline_integration(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock Gemini responses
        mock_scoring_resp = MagicMock()
        mock_scoring_resp.text = """
        [
          {
            "index": 0,
            "category": "Implantology",
            "clinical_relevance": 9,
            "scientific_credibility": 9,
            "educational_value": 8,
            "innovation_significance": 9,
            "public_interest": 7,
            "practical_patient_relevance": 8,
            "is_promotional": false,
            "is_low_quality": false,
            "reasoning": "Clinical breakthrough."
          },
          {
            "index": 1,
            "category": "Preventive dentistry",
            "clinical_relevance": 8,
            "scientific_credibility": 8,
            "educational_value": 9,
            "innovation_significance": 6,
            "public_interest": 8,
            "practical_patient_relevance": 9,
            "is_promotional": false,
            "is_low_quality": false,
            "reasoning": "Educational patient value."
          }
        ]
        """
        
        mock_selection_resp = MagicMock()
        mock_selection_resp.text = '{"selected_index": 0, "rationale": "High clinical value"}'
        
        # Long English text to pass the 300-word constraint
        en_content = " ".join(["Dentplant is committed to modern dentistry. Here is some clinical text about implants."] * 30)
        mock_writing_en_resp = MagicMock()
        mock_writing_en_resp.text = f"TITLE: Innovative Dental Implants\nTEASER: Engaging lines about dental implants.\nCONTENT:\n{en_content}"
        
        # Long Greek text to pass the 300-word constraint
        el_content = " ".join(["Το Dentplant προσφέρει υπηρεσίες υψηλής ποιότητας. Εδώ είναι ένα κείμενο στα ελληνικά για τα εμφυτεύματα."] * 25)
        mock_writing_el_resp = MagicMock()
        mock_writing_el_resp.text = f"TITLE: Καινοτόμα Οδοντικά Εμφυτεύματα\nTEASER: Ενημερωτικές γραμμές για τα εμφυτεύματα.\nCONTENT:\n{el_content}"
        
        mock_qa_resp = MagicMock()
        mock_qa_resp.text = '{"is_valid": true, "errors": []}'
        
        mock_client.models.generate_content.side_effect = [
            mock_scoring_resp,
            mock_selection_resp,
            mock_writing_en_resp,
            mock_writing_el_resp,
            mock_qa_resp
        ]
        
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'mock_key'}):
            result = generator.generate_blog_post(
                [self.sample_articles[0], self.sample_articles[2]], 
                practice_name="Dentplant", 
                recent_posts=[]
            )
            
            self.assertIn("--- ENGLISH VERSION ---", result)
            self.assertIn("--- GREEK VERSION ---", result)
            self.assertIn("Dentplant", result)
            self.assertEqual(mock_client.models.generate_content.call_count, 5)

    def test_create_google_post_assets(self):
        import shutil
        import os
        import publisher
        
        test_data = {
            "image_url": "https://example.com/test.jpg",
            "en": {
                "title": "English Title Test",
                "teaser": "English Teaser Test"
            },
            "el": {
                "title": "Greek Title Test",
                "teaser": "Greek Teaser Test"
            }
        }
        test_file_name = "test-news-file.html"
        
        # Override BASE_DIR temporarily
        import tempfile
        from PIL import Image
        temp_base_dir = tempfile.mkdtemp()
        old_base_dir = publisher.BASE_DIR
        publisher.BASE_DIR = temp_base_dir
        
        google_post_dir = None
        try:
            # Create a test image
            temp_img_path = os.path.join(temp_base_dir, "test_image.png")
            img = Image.new("RGBA", (100, 100), color="blue")
            img.save(temp_img_path)
            
            # Call the asset creator with the test image path
            google_post_dir = publisher.create_google_post_assets(test_data, test_file_name, "test_image.png")
            
            # Verify the directory was created
            self.assertIsNotNone(google_post_dir)
            self.assertTrue(os.path.exists(google_post_dir))
            
            # Verify the expected files were created (including photo.jpg)
            self.assertTrue(os.path.exists(os.path.join(google_post_dir, "cta_url.txt")))
            self.assertTrue(os.path.exists(os.path.join(google_post_dir, "photo_link.txt")))
            self.assertTrue(os.path.exists(os.path.join(google_post_dir, "photo.jpg")))
            self.assertFalse(os.path.exists(os.path.join(google_post_dir, "post_content_el.txt")))
            self.assertFalse(os.path.exists(os.path.join(google_post_dir, "post_content_en.txt")))
            self.assertTrue(os.path.exists(os.path.join(google_post_dir, "post_content_combined.txt")))
            
            # Check CTA URL content
            with open(os.path.join(google_post_dir, "cta_url.txt"), "r", encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), "https://www.dentplant.gr/article/test-news-file.html")
                
            # Check Combined Post content
            with open(os.path.join(google_post_dir, "post_content_combined.txt"), "r", encoding="utf-8") as f:
                combined_content = f.read()
                self.assertIn("📢 Greek Title Test", combined_content)
                self.assertIn("Greek Teaser Test", combined_content)
                self.assertIn("📢 English Title Test", combined_content)
                self.assertIn("English Teaser Test", combined_content)
        finally:
            # Clean up created files
            if google_post_dir and os.path.exists(google_post_dir):
                shutil.rmtree(google_post_dir)
            publisher.BASE_DIR = old_base_dir
            shutil.rmtree(temp_base_dir)

if __name__ == "__main__":
    unittest.main()
