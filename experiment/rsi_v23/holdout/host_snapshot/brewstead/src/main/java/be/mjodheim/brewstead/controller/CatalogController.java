package be.mjodheim.brewstead.controller;

import be.mjodheim.brewstead.dto.catalog.CropResponse;
import be.mjodheim.brewstead.dto.catalog.IngredientCatalogResponse;
import be.mjodheim.brewstead.service.CatalogService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/catalog")
@RequiredArgsConstructor
public class CatalogController {

    private final CatalogService catalogService;

    @GetMapping("/ingredients")
    public List<IngredientCatalogResponse> ingredients() {
        return catalogService.findAllIngredients();
    }

    @GetMapping("/crops")
    public List<CropResponse> crops() {
        return catalogService.findAllCrops();
    }
}
